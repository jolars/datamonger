//! C ABI 1. The public contract and ownership rules are in include/datamonger.h.
//!
//! Unsafe code is confined to borrowing caller-owned slices and result handles.
//! The decoder and canonical encoder themselves live in the safe core crate.
#![allow(clippy::missing_safety_doc)]

use std::ffi::c_void;
use std::fs::File;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;
use std::slice;

use datamonger_core::{
    artifact_reader, canonical_sha256, decode_delimited_with_options,
    decode_libsvm_split_version_with_options, decode_libsvm_split_with_options,
    decode_libsvm_version_with_options, decode_libsvm_with_options, write_canonical, Column,
    Component, Compression, DataType, DecodeOptions, DelimitedOptions, Error, ErrorKind, LabelType,
    LibsvmOptions, Result, Shape, Values,
};

const JULIA_NUMBERS: DecodeOptions = DecodeOptions {
    reject_float_underflow: true,
};

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmBytes {
    pub data: *const u8,
    pub len: usize,
}
impl DmBytes {
    fn new(bytes: &[u8]) -> Self {
        Self {
            data: bytes.as_ptr(),
            len: bytes.len(),
        }
    }
    const EMPTY: Self = Self {
        data: ptr::null(),
        len: 0,
    };
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmU64s {
    pub data: *const u64,
    pub len: usize,
}
impl DmU64s {
    fn new(values: &[u64]) -> Self {
        Self {
            data: values.as_ptr(),
            len: values.len(),
        }
    }
    const EMPTY: Self = Self {
        data: ptr::null(),
        len: 0,
    };
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmColumn {
    pub name: DmBytes,
    pub data_type: u32,
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmDelimitedOptions {
    pub delimiter: u32,
    pub columns: *const DmColumn,
    pub column_count: usize,
    pub missing_values: *const DmBytes,
    pub missing_count: usize,
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmLibsvmOptions {
    pub feature_count: u64,
    pub label_type: u32,
    pub target_name: DmBytes,
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmArtifact {
    pub path: DmBytes,
    pub compression: u32,
}
#[repr(C)]
#[derive(Clone, Copy)]
pub struct DmComponent {
    pub name: DmBytes,
    pub kind: u32,
    pub data_type: u32,
    pub rows: u64,
    pub columns: u64,
    pub values: *const c_void,
    pub len: usize,
    pub valid: DmBytes,
    pub row_offsets: DmU64s,
    pub column_indices: DmU64s,
}

// These buffers are never resized after the views have been constructed. Moving
// the owning result does not move any of its heap-allocated backing buffers.
pub struct DmResult {
    status: u32,
    error: String,
    _components: Vec<Component>,
    _valid: Vec<Vec<u8>>,
    _strings: Vec<Vec<DmBytes>>,
    _bools: Vec<Vec<u8>>,
    views: Vec<DmComponent>,
    digest: Vec<u8>,
    bytes: Vec<u8>,
}
impl DmResult {
    fn new(components: Vec<Component>) -> Self {
        let valid: Vec<Vec<u8>> = components
            .iter()
            .map(|c| c.valid.iter().map(|&v| u8::from(v)).collect())
            .collect();
        let strings: Vec<Vec<DmBytes>> = components
            .iter()
            .map(|c| match &c.values {
                Values::String(v) => v.iter().map(|s| DmBytes::new(s.as_bytes())).collect(),
                _ => Vec::new(),
            })
            .collect();
        // Vec<bool> has no C representation, so expose explicit bytes instead.
        let bools: Vec<Vec<u8>> = components
            .iter()
            .map(|c| match &c.values {
                Values::Bool(v) => v.iter().map(|&v| u8::from(v)).collect(),
                _ => Vec::new(),
            })
            .collect();
        let views = components
            .iter()
            .enumerate()
            .map(|(i, c)| {
                let (kind, rows, columns, row_offsets, column_indices) = match &c.shape {
                    Shape::Vector => (1, c.values.len() as u64, 1, DmU64s::EMPTY, DmU64s::EMPTY),
                    Shape::Dense { rows, columns } => {
                        (3, *rows, *columns, DmU64s::EMPTY, DmU64s::EMPTY)
                    }
                    Shape::Sparse {
                        rows,
                        columns,
                        row_offsets,
                        column_indices,
                    } => (
                        2,
                        *rows,
                        *columns,
                        DmU64s::new(row_offsets),
                        DmU64s::new(column_indices),
                    ),
                };
                let (data_type, values) = match &c.values {
                    Values::Float64(v) => (1, v.as_ptr().cast()),
                    Values::Int64(v) => (2, v.as_ptr().cast()),
                    Values::String(_) => (3, strings[i].as_ptr().cast()),
                    Values::Bool(_) => (4, bools[i].as_ptr().cast()),
                };
                DmComponent {
                    name: DmBytes::new(c.name.as_bytes()),
                    kind,
                    data_type,
                    rows,
                    columns,
                    values,
                    len: c.values.len(),
                    valid: DmBytes::new(&valid[i]),
                    row_offsets,
                    column_indices,
                }
            })
            .collect();
        Self {
            status: 0,
            error: String::new(),
            _components: components,
            _valid: valid,
            _strings: strings,
            _bools: bools,
            views,
            digest: Vec::new(),
            bytes: Vec::new(),
        }
    }
    fn error(error: Error) -> Self {
        let mut result = Self::new(Vec::new());
        result.status = match error.kind {
            ErrorKind::UnsupportedDecoder => 1,
            ErrorKind::DecodedIntegrity => 3,
            _ => 2,
        };
        result.error = error.to_string();
        result
    }
}
fn boundary(f: impl FnOnce() -> Result<DmResult>) -> *mut DmResult {
    let result = match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(result)) => result,
        Ok(Err(error)) => DmResult::error(error),
        Err(_) => {
            let mut result = DmResult::new(Vec::new());
            result.status = 4;
            result.error = "internal native panic".into();
            result
        }
    };
    Box::into_raw(Box::new(result))
}
fn invalid(kind: ErrorKind, message: &str) -> Error {
    Error::new(kind, message)
}

// The caller guarantees readable storage. Check mechanical slice constraints
// before invoking from_raw_parts, including for malformed ABI requests.
unsafe fn borrow<'a, T>(data: *const T, len: usize, kind: ErrorKind) -> Result<&'a [T]> {
    if len == 0 {
        return Ok(&[]);
    }
    if data.is_null()
        || (data as usize) % align_of::<T>() != 0
        || len > isize::MAX as usize / size_of::<T>()
    {
        return Err(invalid(kind, "invalid native buffer"));
    }
    Ok(unsafe { slice::from_raw_parts(data, len) })
}
unsafe fn text(bytes: DmBytes, kind: ErrorKind) -> Result<String> {
    let bytes = unsafe { borrow(bytes.data, bytes.len, kind)? };
    String::from_utf8(bytes.to_vec()).map_err(|_| invalid(kind, "invalid UTF-8 in native request"))
}
fn data_type(tag: u32, kind: ErrorKind) -> Result<DataType> {
    match tag {
        1 => Ok(DataType::Float64),
        2 => Ok(DataType::Int64),
        3 => Ok(DataType::String),
        4 => Ok(DataType::Bool),
        _ => Err(invalid(kind, "invalid logical type")),
    }
}
unsafe fn reader(artifact: DmArtifact) -> Result<Box<dyn std::io::BufRead>> {
    let compression = match artifact.compression {
        0 => Compression::None,
        1 => Compression::Gzip,
        2 => Compression::Bzip2,
        _ => {
            return Err(invalid(
                ErrorKind::UnsupportedDecoder,
                "unsupported artifact compression",
            ))
        }
    };
    let path = unsafe { text(artifact.path, ErrorKind::Decode)? };
    Ok(artifact_reader(File::open(path)?, compression))
}
unsafe fn svm_options(options: DmLibsvmOptions) -> Result<LibsvmOptions> {
    let kind = ErrorKind::UnsupportedDecoder;
    let label_type = match options.label_type {
        1 => LabelType::Float64,
        2 => LabelType::Int64,
        _ => return Err(invalid(kind, "invalid label type")),
    };
    Ok(LibsvmOptions {
        feature_count: options.feature_count,
        label_type,
        target_name: unsafe { text(options.target_name, kind)? },
    })
}

#[no_mangle]
pub extern "C" fn dm_abi_version() -> u32 {
    1
}

#[no_mangle]
pub unsafe extern "C" fn dm_decode_delimited(
    artifact: DmArtifact,
    options: DmDelimitedOptions,
) -> *mut DmResult {
    boundary(|| {
        let kind = ErrorKind::UnsupportedDecoder;
        let columns = unsafe { borrow(options.columns, options.column_count, kind)? }
            .iter()
            .map(|c| {
                Ok(Column {
                    name: unsafe { text(c.name, kind)? },
                    data_type: data_type(c.data_type, kind)?,
                })
            })
            .collect::<Result<_>>()?;
        let missing_values =
            unsafe { borrow(options.missing_values, options.missing_count, kind)? }
                .iter()
                .map(|&v| unsafe { text(v, kind) })
                .collect::<Result<_>>()?;
        let delimiter =
            u8::try_from(options.delimiter).map_err(|_| invalid(kind, "invalid delimiter"))?;
        let options = DelimitedOptions {
            delimiter,
            columns,
            missing_values,
        };
        Ok(DmResult::new(decode_delimited_with_options(
            unsafe { reader(artifact)? },
            &options,
            JULIA_NUMBERS,
        )?))
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_decode_libsvm(
    artifact: DmArtifact,
    options: DmLibsvmOptions,
    prefix: DmBytes,
) -> *mut DmResult {
    boundary(|| {
        let options = unsafe { svm_options(options)? };
        let prefix = unsafe { text(prefix, ErrorKind::UnsupportedDecoder)? };
        let mut components =
            decode_libsvm_with_options(unsafe { reader(artifact)? }, &options, JULIA_NUMBERS)?;
        for component in &mut components {
            component.name.insert_str(0, &prefix);
        }
        Ok(DmResult::new(components))
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_decode_libsvm_split(
    train: DmArtifact,
    test: DmArtifact,
    options: DmLibsvmOptions,
) -> *mut DmResult {
    boundary(|| {
        let options = unsafe { svm_options(options)? };
        Ok(DmResult::new(decode_libsvm_split_with_options(
            unsafe { reader(train)? },
            unsafe { reader(test)? },
            &options,
            JULIA_NUMBERS,
        )?))
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_decode_libsvm_v2(
    artifact: DmArtifact,
    options: DmLibsvmOptions,
    prefix: DmBytes,
) -> *mut DmResult {
    boundary(|| {
        let options = unsafe { svm_options(options)? };
        let prefix = unsafe { text(prefix, ErrorKind::UnsupportedDecoder)? };
        let mut components = decode_libsvm_version_with_options(
            unsafe { reader(artifact)? },
            &options,
            2,
            JULIA_NUMBERS,
        )?;
        for component in &mut components {
            component.name.insert_str(0, &prefix);
        }
        Ok(DmResult::new(components))
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_decode_libsvm_split_v2(
    train: DmArtifact,
    test: DmArtifact,
    options: DmLibsvmOptions,
) -> *mut DmResult {
    boundary(|| {
        let options = unsafe { svm_options(options)? };
        Ok(DmResult::new(decode_libsvm_split_version_with_options(
            unsafe { reader(train)? },
            unsafe { reader(test)? },
            &options,
            2,
            JULIA_NUMBERS,
        )?))
    })
}
unsafe fn component(view: &DmComponent) -> Result<Component> {
    let kind = ErrorKind::DecodedIntegrity;
    let name = unsafe { text(view.name, kind)? };
    let valid_bytes = unsafe { borrow(view.valid.data, view.valid.len, kind)? };
    if valid_bytes.iter().any(|&v| v > 1) {
        return Err(invalid(kind, "validity bytes must be 0 or 1"));
    }
    let valid = valid_bytes.iter().map(|&v| v != 0).collect();
    let values = match data_type(view.data_type, kind)? {
        DataType::Float64 => {
            Values::Float64(unsafe { borrow(view.values.cast(), view.len, kind)? }.to_vec())
        }
        DataType::Int64 => {
            Values::Int64(unsafe { borrow(view.values.cast(), view.len, kind)? }.to_vec())
        }
        DataType::String => Values::String(
            unsafe { borrow(view.values.cast::<DmBytes>(), view.len, kind)? }
                .iter()
                .enumerate()
                .map(|(i, &v)| {
                    // Invalid string storage is not interpreted by the canonical form.
                    if valid_bytes.get(i) == Some(&0) {
                        Ok(String::new())
                    } else {
                        unsafe { text(v, kind) }
                    }
                })
                .collect::<Result<_>>()?,
        ),
        DataType::Bool => {
            let bytes: &[u8] = unsafe { borrow(view.values.cast(), view.len, kind)? };
            if bytes.iter().any(|&v| v > 1) {
                return Err(invalid(kind, "boolean bytes must be 0 or 1"));
            }
            Values::Bool(bytes.iter().map(|&v| v != 0).collect())
        }
    };
    let shape = match view.kind {
        1 => {
            if view.rows != view.len as u64 || view.columns != 1 {
                return Err(invalid(kind, "invalid vector dimensions"));
            }
            Shape::Vector
        }
        3 => Shape::Dense {
            rows: view.rows,
            columns: view.columns,
        },
        2 => Shape::Sparse {
            rows: view.rows,
            columns: view.columns,
            row_offsets: unsafe { borrow(view.row_offsets.data, view.row_offsets.len, kind)? }
                .to_vec(),
            column_indices: unsafe {
                borrow(view.column_indices.data, view.column_indices.len, kind)?
            }
            .to_vec(),
        },
        _ => return Err(invalid(kind, "invalid component kind")),
    };
    Ok(Component {
        name,
        shape,
        values,
        valid,
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_canonical(
    views: *const DmComponent,
    count: usize,
    emit_bytes: u32,
) -> *mut DmResult {
    boundary(|| {
        if emit_bytes > 1 {
            return Err(invalid(
                ErrorKind::DecodedIntegrity,
                "invalid canonical output mode",
            ));
        }
        let components = unsafe { borrow(views, count, ErrorKind::DecodedIntegrity)? }
            .iter()
            .map(|v| unsafe { component(v) })
            .collect::<Result<Vec<_>>>()?;
        let digest = canonical_sha256(&components)?.to_vec();
        let mut bytes = Vec::new();
        if emit_bytes == 1 {
            write_canonical(&components, &mut bytes)?;
        }
        let mut result = DmResult::new(Vec::new());
        result.digest = digest;
        result.bytes = bytes;
        Ok(result)
    })
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_status(result: *const DmResult) -> u32 {
    unsafe { result.as_ref() }.map_or(4, |r| r.status)
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_error(result: *const DmResult) -> DmBytes {
    unsafe { result.as_ref() }.map_or(DmBytes::EMPTY, |r| DmBytes::new(r.error.as_bytes()))
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_count(result: *const DmResult) -> usize {
    unsafe { result.as_ref() }.map_or(0, |r| r.views.len())
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_component(
    result: *const DmResult,
    index: usize,
) -> *const DmComponent {
    unsafe { result.as_ref() }
        .and_then(|r| r.views.get(index))
        .map_or(ptr::null(), |v| v)
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_digest(result: *const DmResult) -> DmBytes {
    unsafe { result.as_ref() }.map_or(DmBytes::EMPTY, |r| DmBytes::new(&r.digest))
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_bytes(result: *const DmResult) -> DmBytes {
    unsafe { result.as_ref() }.map_or(DmBytes::EMPTY, |r| DmBytes::new(&r.bytes))
}
#[no_mangle]
pub unsafe extern "C" fn dm_result_free(result: *mut DmResult) {
    if !result.is_null() {
        drop(unsafe { Box::from_raw(result) });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn panic_is_contained() {
        let result = boundary(|| panic!("test panic"));
        unsafe {
            assert_eq!(dm_result_status(result), 4);
            dm_result_free(result);
        }
    }
    #[test]
    fn null_and_invalid_buffers() {
        unsafe {
            assert_eq!(dm_result_status(ptr::null()), 4);
            assert!(dm_result_component(ptr::null(), 0).is_null());
            dm_result_free(ptr::null_mut());
            let result = dm_canonical(ptr::null(), 1, 0);
            assert_eq!(dm_result_status(result), 3);
            dm_result_free(result);
            let result = dm_canonical(ptr::null(), 0, 0);
            assert_eq!(dm_result_status(result), 0);
            assert_eq!(dm_result_digest(result).len, 32);
            assert_eq!(dm_result_bytes(result).len, 0);
            dm_result_free(result);
        }
    }
}
