use std::collections::HashSet;
use std::io::Write;

use sha2::{Digest, Sha256};

use crate::{Component, Control, Error, ErrorKind, Result, Shape, Values};

/// Maximum number of canonical bytes emitted in a single writer call.
pub const EMIT_BYTES: usize = 65536;

fn invalid(message: &str) -> Error {
    Error::new(ErrorKind::DecodedIntegrity, message)
}

struct Emitter<'a, W, C> {
    writer: W,
    control: &'a mut C,
    buffer: Vec<u8>,
}

impl<W: Write, C: Control> Emitter<'_, W, C> {
    fn flush(&mut self) -> Result<()> {
        self.control.checkpoint()?;
        self.writer.write_all(&self.buffer)?;
        self.buffer.clear();
        Ok(())
    }
    fn bytes(&mut self, mut bytes: &[u8]) -> Result<()> {
        while !bytes.is_empty() {
            let count = bytes.len().min(EMIT_BYTES - self.buffer.len());
            self.buffer.extend_from_slice(&bytes[..count]);
            bytes = &bytes[count..];
            if self.buffer.len() == EMIT_BYTES {
                self.flush()?;
            }
        }
        Ok(())
    }
    fn u64(&mut self, value: u64) -> Result<()> {
        self.bytes(&value.to_le_bytes())
    }
    fn float(&mut self, value: f64) -> Result<()> {
        let word = if value.is_nan() {
            0x7ff8000000000000
        } else if value == 0.0 {
            0
        } else if value.is_finite() {
            value.to_bits()
        } else {
            return Err(invalid("canonical float64 value is infinite"));
        };
        self.u64(word)
    }
    fn bitmap(&mut self, len: usize, bit: impl Fn(usize) -> bool) -> Result<()> {
        for start in (0..len).step_by(8) {
            let mut byte = 0;
            for index in start..(start + 8).min(len) {
                if bit(index) {
                    byte |= 1 << (index - start);
                }
            }
            self.bytes(&[byte])?;
        }
        Ok(())
    }
    fn values(&mut self, values: &Values, valid: &[bool]) -> Result<()> {
        if values.len() != valid.len() {
            return Err(invalid("component values and validity disagree"));
        }
        self.bitmap(valid.len(), |i| valid[i])?;
        match values {
            Values::Float64(values) => {
                for (&value, &valid) in values.iter().zip(valid) {
                    self.float(if valid { value } else { 0.0 })?;
                }
            }
            Values::Int64(values) => {
                for (&value, &valid) in values.iter().zip(valid) {
                    self.bytes(&if valid { value } else { 0 }.to_le_bytes())?;
                }
            }
            Values::String(values) => {
                for (value, &valid) in values.iter().zip(valid) {
                    let bytes = if valid { value.as_bytes() } else { &[] };
                    self.u64(bytes.len() as u64)?;
                    self.bytes(bytes)?;
                }
            }
            Values::Bool(values) => self.bitmap(values.len(), |i| valid[i] && values[i])?,
        }
        Ok(())
    }
    fn component(&mut self, component: &Component) -> Result<()> {
        let name_length = u32::try_from(component.name.len())
            .map_err(|_| invalid("component name is too long"))?;
        self.bytes(&name_length.to_le_bytes())?;
        self.bytes(component.name.as_bytes())?;
        let type_tag = match component.values {
            Values::Float64(_) => 1,
            Values::Int64(_) => 2,
            Values::String(_) => 3,
            Values::Bool(_) => 4,
        };
        match &component.shape {
            Shape::Vector => {
                self.bytes(&[1, type_tag, 1])?;
                self.u64(component.values.len() as u64)?;
                self.values(&component.values, &component.valid)?;
            }
            Shape::Dense { rows, columns } => {
                if rows.checked_mul(*columns) != Some(component.values.len() as u64) {
                    return Err(invalid("dense dimensions and values disagree"));
                }
                self.bytes(&[3, type_tag, 2])?;
                self.u64(*rows)?;
                self.u64(*columns)?;
                self.values(&component.values, &component.valid)?;
            }
            Shape::Sparse {
                rows,
                columns,
                row_offsets,
                column_indices,
            } => {
                let Values::Float64(values) = &component.values else {
                    return Err(invalid("sparse matrices must contain float64"));
                };
                let nnz = values.len() as u64;
                if !component.valid.is_empty()
                    || rows.checked_add(1) != Some(row_offsets.len() as u64)
                    || column_indices.len() != values.len()
                    || row_offsets.first() != Some(&0)
                    || row_offsets.last() != Some(&nnz)
                    || row_offsets.windows(2).any(|w| w[0] > w[1] || w[1] > nnz)
                    || column_indices.iter().any(|&index| index >= *columns)
                    || values.iter().any(|v| v.is_infinite() || *v == 0.0)
                {
                    return Err(invalid("invalid canonical sparse matrix"));
                }
                for (row, offsets) in row_offsets.windows(2).enumerate() {
                    if column_indices[offsets[0] as usize..offsets[1] as usize]
                        .windows(2)
                        .any(|w| w[0] >= w[1])
                    {
                        return Err(invalid("sparse indices must increase within rows"));
                    }
                    if row % 1024 == 0 {
                        self.control.checkpoint()?;
                    }
                }
                self.bytes(&[2, 1, 2])?;
                self.u64(*rows)?;
                self.u64(*columns)?;
                self.u64(nnz)?;
                for &offset in row_offsets {
                    self.u64(offset)?;
                }
                for &index in column_indices {
                    self.u64(index)?;
                }
                for &value in values {
                    self.float(value)?;
                }
            }
        }
        Ok(())
    }
}

/// Write canonical form version 1, with bounded temporary storage.
pub fn write_canonical(components: &[Component], writer: impl Write) -> Result<()> {
    write_canonical_with_control(components, writer, &mut || Ok(()))
}

/// Write canonical form version 1 with cancellation between emission chunks.
pub fn write_canonical_with_control(
    components: &[Component],
    writer: impl Write,
    control: &mut impl Control,
) -> Result<()> {
    control.checkpoint()?;
    let count = u32::try_from(components.len()).map_err(|_| invalid("too many components"))?;
    let mut names = HashSet::new();
    if components
        .iter()
        .any(|c| c.name.is_empty() || !names.insert(&c.name))
    {
        return Err(invalid("component names must be nonempty and unique"));
    }
    let mut emitter = Emitter {
        writer,
        control,
        buffer: Vec::with_capacity(EMIT_BYTES),
    };
    emitter.bytes(b"DMCF\x01\x00")?;
    emitter.bytes(&count.to_le_bytes())?;
    for component in components {
        emitter.component(component)?;
    }
    emitter.flush()
}

struct HashWriter(Sha256);
impl Write for HashWriter {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.0.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

/// SHA-256 of canonical form version 1, without retaining the stream.
pub fn canonical_sha256(components: &[Component]) -> Result<[u8; 32]> {
    canonical_sha256_with_control(components, &mut || Ok(()))
}

/// Hash canonical form version 1 with cancellation checkpoints.
pub fn canonical_sha256_with_control(
    components: &[Component],
    control: &mut impl Control,
) -> Result<[u8; 32]> {
    let mut writer = HashWriter(Sha256::new());
    write_canonical_with_control(components, &mut writer, control)?;
    Ok(writer.0.finalize().into())
}
