//! Private R conversions. The reusable decoder has no dependency on this crate.

use std::ffi::{c_int, c_void};
use std::fs::File;
use std::io::Cursor;

use datamonger_core as core;
use extendr_api::prelude::*;

extern "C" {
    fn R_CheckUserInterrupt();
    fn R_ToplevelExec(fun: Option<unsafe extern "C" fn(*mut c_void)>, data: *mut c_void) -> c_int;
}

unsafe extern "C" fn check_interrupt(_: *mut c_void) {
    // This callback owns nothing: R's jump returns to R_ToplevelExec without
    // bypassing any Rust destructor or leaving a borrowed buffer in use.
    unsafe { R_CheckUserInterrupt() };
}

fn checkpoint() -> core::Result<()> {
    // Catch an R interrupt inside R before returning an ordinary Rust error.
    if unsafe { R_ToplevelExec(Some(check_interrupt), std::ptr::null_mut()) } == 0 {
        Err(core::Error::new(
            core::ErrorKind::Interrupted,
            "interrupted",
        ))
    } else {
        Ok(())
    }
}

fn invalid(message: impl Into<String>) -> core::Error {
    core::Error::new(core::ErrorKind::DecodedIntegrity, message)
}

fn field(list: &List, name: &str) -> core::Result<Robj> {
    list.iter()
        .find(|(key, _)| *key == name)
        .map(|(_, value)| value)
        .ok_or_else(|| invalid(format!("missing field '{name}'")))
}

fn string(value: &Robj) -> core::Result<String> {
    value
        .as_str()
        .map(str::to_owned)
        .ok_or_else(|| invalid("expected a nonmissing string"))
}

fn strings(value: &Robj) -> core::Result<Vec<String>> {
    value
        .as_str_vector()
        .ok_or_else(|| invalid("expected strings"))
        .map(|values| values.into_iter().map(str::to_owned).collect())
}

fn numbers(value: &Robj) -> core::Result<Vec<f64>> {
    if let Some(values) = value.as_real_slice() {
        return Ok(values.to_vec());
    }
    if let Some(values) = value.as_integer_slice() {
        return Ok(values.iter().map(|&x| x as f64).collect());
    }
    Err(invalid("expected numeric values"))
}

fn unsigned(value: f64) -> core::Result<u64> {
    if !value.is_finite()
        || value < 0.0
        || value.fract() != 0.0
        || value > ((1_u64 << 53) - 1) as f64
    {
        return Err(invalid(
            "dimension or index is outside R's exact integer range",
        ));
    }
    Ok(value as u64)
}

fn dimension(list: &List, name: &str) -> core::Result<u64> {
    let values = numbers(&field(list, name)?)?;
    if values.len() != 1 {
        return Err(invalid("dimension must be a scalar"));
    }
    unsigned(values[0])
}

fn bools(value: &Robj) -> core::Result<Vec<bool>> {
    let values = value
        .as_logical_slice()
        .ok_or_else(|| invalid("expected logical values"))?;
    values
        .iter()
        .map(|x| {
            if x.is_na() {
                Err(invalid("validity cannot be missing"))
            } else {
                Ok(x.is_true())
            }
        })
        .collect()
}

fn data_type(value: &str) -> core::Result<core::DataType> {
    match value {
        "float64" => Ok(core::DataType::Float64),
        "int64" => Ok(core::DataType::Int64),
        "string" => Ok(core::DataType::String),
        "bool" => Ok(core::DataType::Bool),
        _ => Err(invalid("unsupported logical type")),
    }
}

fn compression(value: &str) -> core::Result<core::Compression> {
    match value {
        "none" => Ok(core::Compression::None),
        "gzip" => Ok(core::Compression::Gzip),
        "bzip2" => Ok(core::Compression::Bzip2),
        _ => Err(core::Error::new(
            core::ErrorKind::UnsupportedDecoder,
            "unsupported artifact compression",
        )),
    }
}

fn reader(path: &str, coding: &str) -> core::Result<Box<dyn std::io::BufRead>> {
    Ok(core::artifact_reader(
        File::open(path)?,
        compression(coding)?,
    ))
}

fn delimited_options(options: &List) -> core::Result<core::DelimitedOptions> {
    let columns = field(options, "columns")?
        .as_list()
        .ok_or_else(|| invalid("expected columns"))?;
    let columns = columns
        .values()
        .map(|column| {
            let column = column.as_list().ok_or_else(|| invalid("invalid column"))?;
            Ok(core::Column {
                name: string(&field(&column, "name")?)?,
                data_type: data_type(&string(&field(&column, "type")?)?)?,
            })
        })
        .collect::<core::Result<Vec<_>>>()?;
    let delimiter = string(&field(options, "delimiter")?)?;
    if delimiter.len() != 1 {
        return Err(invalid("invalid delimiter"));
    }
    let missing = field(options, "missing_values")?;
    Ok(core::DelimitedOptions {
        delimiter: delimiter.as_bytes()[0],
        columns,
        missing_values: if missing.is_null() {
            Vec::new()
        } else {
            strings(&missing)?
        },
    })
}

fn libsvm_options(options: &List) -> core::Result<core::LibsvmOptions> {
    let label = match string(&field(options, "label_type")?)?.as_str() {
        "int64" => core::LabelType::Int64,
        "float64" => core::LabelType::Float64,
        _ => return Err(invalid("unsupported label type")),
    };
    Ok(core::LibsvmOptions {
        feature_count: dimension(options, "feature_count")?,
        label_type: label,
        target_name: string(&field(options, "target_name")?)?,
    })
}

fn values_to_r(values: &core::Values) -> Robj {
    match values {
        core::Values::Float64(v) => v.iter().copied().collect_robj(),
        core::Values::Int64(v) => v.iter().map(i64::to_string).collect_robj(),
        core::Values::String(v) => v.iter().map(String::as_str).collect_robj(),
        core::Values::Bool(v) => v.iter().copied().collect_robj(),
    }
}

fn component_to_r(component: &core::Component) -> core::Result<Robj> {
    // R strings cannot contain NUL even though the Rust logical model can.
    if component.name.contains('\0')
        || matches!(&component.values, core::Values::String(v) if v.iter().any(|s| s.contains('\0')))
    {
        return Err(core::Error::new(
            core::ErrorKind::Decode,
            "R cannot represent embedded NUL in strings",
        ));
    }
    let logical_type = match component.values.data_type() {
        core::DataType::Float64 => "float64",
        core::DataType::Int64 => "int64",
        core::DataType::String => "string",
        core::DataType::Bool => "bool",
    };
    let values = values_to_r(&component.values);
    let mut result = match &component.shape {
        core::Shape::Vector => list!(
            name = component.name.clone(),
            kind = "vector",
            logical_type = logical_type,
            values = values,
            valid = component.valid.clone()
        ),
        core::Shape::Dense { rows, columns } => list!(
            name = component.name.clone(),
            kind = "dense_matrix",
            logical_type = logical_type,
            rows = *rows as f64,
            columns = *columns as f64,
            values = values,
            valid = component.valid.clone()
        ),
        core::Shape::Sparse {
            rows,
            columns,
            row_offsets,
            column_indices,
        } => list!(
            name = component.name.clone(),
            kind = "sparse_matrix",
            logical_type = logical_type,
            rows = *rows as f64,
            columns = *columns as f64,
            row_offsets = row_offsets.iter().map(|&v| v as f64).collect::<Vec<_>>(),
            column_indices = column_indices.iter().map(|&v| v as f64).collect::<Vec<_>>(),
            values = values
        ),
    };
    result
        .set_class(["datamonger_logical_component"])
        .map_err(|e| invalid(e.to_string()))?;
    Ok(result.into())
}

fn component_from_r(value: Robj) -> core::Result<core::Component> {
    let list = value
        .as_list()
        .ok_or_else(|| invalid("expected a logical component"))?;
    let name = string(&field(&list, "name")?)?;
    let logical_type = string(&field(&list, "logical_type")?)?;
    let raw = field(&list, "values")?;
    let values = match data_type(&logical_type)? {
        core::DataType::Float64 => core::Values::Float64(numbers(&raw)?),
        core::DataType::Int64 => core::Values::Int64(
            strings(&raw)?
                .iter()
                .map(|s| {
                    s.parse::<i64>()
                        .map_err(|_| invalid("int64 value is out of range"))
                })
                .collect::<core::Result<Vec<_>>>()?,
        ),
        core::DataType::String => core::Values::String(strings(&raw)?),
        core::DataType::Bool => core::Values::Bool(bools(&raw)?),
    };
    let kind = string(&field(&list, "kind")?)?;
    let shape = match kind.as_str() {
        "vector" => core::Shape::Vector,
        "dense_matrix" => core::Shape::Dense {
            rows: dimension(&list, "rows")?,
            columns: dimension(&list, "columns")?,
        },
        "sparse_matrix" => core::Shape::Sparse {
            rows: dimension(&list, "rows")?,
            columns: dimension(&list, "columns")?,
            row_offsets: numbers(&field(&list, "row_offsets")?)?
                .into_iter()
                .map(unsigned)
                .collect::<core::Result<_>>()?,
            column_indices: numbers(&field(&list, "column_indices")?)?
                .into_iter()
                .map(unsigned)
                .collect::<core::Result<_>>()?,
        },
        _ => return Err(invalid("unsupported component kind")),
    };
    let valid = if matches!(shape, core::Shape::Sparse { .. }) {
        Vec::new()
    } else {
        bools(&field(&list, "valid")?)?
    };
    Ok(core::Component {
        name,
        shape,
        values,
        valid,
    })
}

fn hex(digest: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    digest
        .iter()
        .flat_map(|b| {
            [
                DIGITS[(b >> 4) as usize] as char,
                DIGITS[(b & 15) as usize] as char,
            ]
        })
        .collect()
}

fn envelope(result: core::Result<Robj>) -> List {
    match result {
        Ok(value) => list!(value = value, category = NULL, message = NULL),
        Err(error) => {
            let inaccessible = std::error::Error::source(&error)
                .and_then(|source| source.downcast_ref::<std::io::Error>())
                .is_some_and(|source| {
                    matches!(
                        source.kind(),
                        std::io::ErrorKind::NotFound | std::io::ErrorKind::PermissionDenied
                    )
                });
            let category = match error.kind {
                core::ErrorKind::Io if inaccessible => "cache",
                core::ErrorKind::UnsupportedDecoder => "unsupported-decoder",
                core::ErrorKind::DecodedIntegrity => "decoded-integrity",
                core::ErrorKind::Interrupted => "interrupted",
                core::ErrorKind::Decode | core::ErrorKind::Io => "decode",
            };
            list!(
                value = NULL,
                category = category,
                message = error.to_string()
            )
        }
    }
}

/// Decode verified artifact paths and optionally hash before converting buffers.
#[extendr]
fn dm_decode(
    decoder: &str,
    paths: Vec<String>,
    compressions: Vec<String>,
    options: List,
    hash: bool,
) -> List {
    envelope((|| {
        if paths.len() != compressions.len() || paths.is_empty() {
            return Err(invalid("invalid artifact inputs"));
        }
        let mut control = checkpoint;
        let components = match decoder {
            "delimited-text" => core::decode_delimited_with_control(
                reader(&paths[0], &compressions[0])?,
                &delimited_options(&options)?,
                &mut control,
            )?,
            "libsvm" => core::decode_libsvm_with_control(
                reader(&paths[0], &compressions[0])?,
                &libsvm_options(&options)?,
                &mut control,
            )?,
            "libsvm-split" if paths.len() == 2 => core::decode_libsvm_split_with_control(
                reader(&paths[0], &compressions[0])?,
                reader(&paths[1], &compressions[1])?,
                &libsvm_options(&options)?,
                &mut control,
            )?,
            _ => {
                return Err(core::Error::new(
                    core::ErrorKind::UnsupportedDecoder,
                    "unsupported decoder or inputs",
                ))
            }
        };
        let digest: Robj = if hash {
            hex(&core::canonical_sha256_with_control(
                &components,
                &mut control,
            )?)
            .into()
        } else {
            NULL.into()
        };
        let converted = components
            .iter()
            .map(component_to_r)
            .collect::<core::Result<Vec<_>>>()?;
        Ok(list!(
            components = List::from_values(converted),
            canonical_digest = digest
        )
        .into())
    })())
}

/// Encode or hash supplied logical components for conformance and diagnostics.
#[extendr]
fn dm_canonical(components: List, hash: bool) -> List {
    envelope((|| {
        let components = components
            .values()
            .map(component_from_r)
            .collect::<core::Result<Vec<_>>>()?;
        if hash {
            Ok(hex(&core::canonical_sha256_with_control(
                &components,
                &mut checkpoint,
            )?)
            .into())
        } else {
            let mut bytes = Vec::new();
            core::write_canonical_with_control(&components, &mut bytes, &mut checkpoint)?;
            Ok(Raw::from_bytes(&bytes).into())
        }
    })())
}

/// Remove a single HTTP gzip content coding.
#[extendr]
fn dm_http_gzip(bytes: Raw) -> List {
    envelope((|| {
        let mut output = Vec::new();
        core::decode_gzip_single_member(Cursor::new(bytes.as_slice()), &mut output)?;
        Ok(Raw::from_bytes(&output).into())
    })())
}

/// Parse a decimal for the R client's rounding regression checks.
#[extendr]
fn dm_parse_binary64(value: &str) -> List {
    envelope(core::parse_binary64(value, true).map(Robj::from))
}

extendr_module! {
    mod datamonger;
    fn dm_decode;
    fn dm_canonical;
    fn dm_http_gzip;
    fn dm_parse_binary64;
}
