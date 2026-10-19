use std::collections::HashSet;
use std::io::BufRead;

use crate::{Component, Control, DataType, Error, ErrorKind, Result, Shape, Values};

/// A declared delimited-text column.
#[derive(Clone, Debug)]
pub struct Column {
    /// Exact header and component name.
    pub name: String,
    /// Declared logical type; no inference is performed.
    pub data_type: DataType,
}

/// The configurable parts of the revision 1 delimited-text recipe.
/// UTF-8, a header, double-quote escaping, and source row order are fixed.
#[derive(Clone, Debug)]
pub struct DelimitedOptions {
    /// Comma or horizontal tab.
    pub delimiter: u8,
    /// Ordered, uniquely named columns.
    pub columns: Vec<Column>,
    /// Exact tokens matched after unquoting and before lexical conversion.
    pub missing_values: Vec<String>,
}

/// LIBSVM response type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LabelType {
    /// Exact signed integers.
    Int64,
    /// Finite binary64 values.
    Float64,
}

/// The configurable parts of the revision 1 LIBSVM recipe.
/// Input indices are one-based; duplicates and stored zeros are errors.
#[derive(Clone, Debug)]
pub struct LibsvmOptions {
    /// Declared feature count, at most `2^53 - 1`.
    pub feature_count: u64,
    /// Response type.
    pub label_type: LabelType,
    /// Response component name, distinct from `features`.
    pub target_name: String,
}

fn decode_error(message: impl Into<String>) -> Error {
    Error::new(ErrorKind::Decode, message)
}

fn unsupported(message: impl Into<String>) -> Error {
    Error::new(ErrorKind::UnsupportedDecoder, message)
}

fn unsigned_decimal(bytes: &[u8]) -> bool {
    !bytes.is_empty()
        && bytes.iter().all(u8::is_ascii_digit)
        && (bytes.len() == 1 || bytes[0] != b'0')
}

fn integer(value: &str, allow_plus: bool) -> Result<i64> {
    let bytes = value.as_bytes();
    let digits = match bytes.first() {
        Some(b'-') => &bytes[1..],
        Some(b'+') if allow_plus => &bytes[1..],
        _ => bytes,
    };
    if !unsigned_decimal(digits) {
        return Err(decode_error(format!("invalid int64 value '{value}'")));
    }
    value
        .parse()
        .map_err(|_| decode_error(format!("int64 value is out of range: '{value}'")))
}

/// Parse the strict revision 1 decimal grammar with correctly rounded binary64
/// conversion. LIBSVM permits a leading plus; delimited text does not.
pub fn parse_binary64(value: &str, allow_plus: bool) -> Result<f64> {
    let bytes = value.as_bytes();
    let mut i = match bytes.first() {
        Some(b'-') => 1,
        Some(b'+') if allow_plus => 1,
        _ => 0,
    };
    let start = i;
    while bytes.get(i).is_some_and(u8::is_ascii_digit) {
        i += 1;
    }
    let mut valid = unsigned_decimal(&bytes[start..i]);
    if bytes.get(i) == Some(&b'.') {
        i += 1;
        let start = i;
        while bytes.get(i).is_some_and(u8::is_ascii_digit) {
            i += 1;
        }
        valid &= i > start;
    }
    if matches!(bytes.get(i), Some(b'e' | b'E')) {
        i += 1;
        if matches!(bytes.get(i), Some(b'+' | b'-')) {
            i += 1;
        }
        let start = i;
        while bytes.get(i).is_some_and(u8::is_ascii_digit) {
            i += 1;
        }
        valid &= i > start;
    }
    if !valid || i != bytes.len() {
        return Err(decode_error(format!("invalid float64 value '{value}'")));
    }
    let parsed: f64 = value
        .parse()
        .map_err(|_| decode_error("invalid float64 value"))?;
    if !parsed.is_finite() {
        return Err(decode_error(format!("non-finite float64 value '{value}'")));
    }
    Ok(parsed)
}

struct Records<R> {
    reader: R,
    buffer: Vec<u8>,
    number: usize,
}

impl<R: BufRead> Records<R> {
    fn new(reader: R) -> Self {
        Self {
            reader,
            buffer: Vec::new(),
            number: 0,
        }
    }
    fn next(&mut self) -> Result<Option<&str>> {
        self.buffer.clear();
        if self.reader.read_until(b'\n', &mut self.buffer)? == 0 {
            return Ok(None);
        }
        self.number += 1;
        if self.buffer.last() == Some(&b'\n') {
            self.buffer.pop();
            if self.buffer.last() == Some(&b'\r') {
                self.buffer.pop();
            }
        }
        if self.buffer.contains(&b'\r') {
            return Err(decode_error(format!(
                "bare carriage return at record {}",
                self.number
            )));
        }
        if self.number == 1 && self.buffer.starts_with(&[0xef, 0xbb, 0xbf]) {
            return Err(decode_error("artifact has a UTF-8 byte-order mark"));
        }
        std::str::from_utf8(&self.buffer)
            .map(Some)
            .map_err(|_| decode_error(format!("invalid UTF-8 at record {}", self.number)))
    }
}

fn fields(record: &str, delimiter: u8) -> Result<Vec<String>> {
    let bytes = record.as_bytes();
    let mut fields = Vec::new();
    let mut i = 0;
    loop {
        let mut value = Vec::new();
        if bytes.get(i) == Some(&b'"') {
            i += 1;
            loop {
                match bytes.get(i) {
                    None => return Err(decode_error("unterminated quoted field")),
                    Some(b'"') if bytes.get(i + 1) == Some(&b'"') => {
                        value.push(b'"');
                        i += 2;
                    }
                    Some(b'"') => {
                        i += 1;
                        break;
                    }
                    Some(&byte) => {
                        value.push(byte);
                        i += 1;
                    }
                }
            }
            if i < bytes.len() && bytes[i] != delimiter {
                return Err(decode_error("closing quote has a trailing suffix"));
            }
        } else {
            let start = i;
            while i < bytes.len() && bytes[i] != delimiter {
                if bytes[i] == b'"' {
                    return Err(decode_error("quote inside unquoted field"));
                }
                i += 1;
            }
            value.extend_from_slice(&bytes[start..i]);
        }
        fields.push(String::from_utf8(value).map_err(|_| decode_error("invalid field UTF-8"))?);
        if i == bytes.len() {
            break;
        }
        i += 1;
    }
    Ok(fields)
}

fn push_value(values: &mut Values, text: &str, valid: bool, allow_plus: bool) -> Result<()> {
    match values {
        Values::Float64(v) => v.push(if valid {
            parse_binary64(text, allow_plus)?
        } else {
            0.0
        }),
        Values::Int64(v) => v.push(if valid { integer(text, allow_plus)? } else { 0 }),
        Values::String(v) => v.push(if valid { text.into() } else { String::new() }),
        Values::Bool(v) => v.push(if !valid {
            false
        } else {
            match text {
                "true" => true,
                "false" => false,
                _ => return Err(decode_error(format!("invalid bool value '{text}'"))),
            }
        }),
    }
    Ok(())
}

/// Decode CSV or TSV using the declared column types and revision 1 grammar.
pub fn decode_delimited<R: BufRead>(
    reader: R,
    options: &DelimitedOptions,
) -> Result<Vec<Component>> {
    decode_delimited_with_control(reader, options, &mut || Ok(()))
}

/// Decode delimited text with cancellation checkpoints between record batches.
pub fn decode_delimited_with_control<R: BufRead>(
    reader: R,
    options: &DelimitedOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    control.checkpoint()?;
    let mut names = HashSet::new();
    if !matches!(options.delimiter, b',' | b'\t')
        || options.columns.is_empty()
        || options
            .columns
            .iter()
            .any(|c| c.name.is_empty() || !names.insert(&c.name))
        || options.missing_values.iter().collect::<HashSet<_>>().len()
            != options.missing_values.len()
    {
        return Err(unsupported("invalid delimited-text recipe"));
    }
    let missing: HashSet<&str> = options.missing_values.iter().map(String::as_str).collect();
    let mut records = Records::new(reader);
    let header = fields(
        records
            .next()?
            .ok_or_else(|| decode_error("delimited artifact is empty"))?,
        options.delimiter,
    )?;
    if header
        .iter()
        .map(String::as_str)
        .ne(options.columns.iter().map(|c| c.name.as_str()))
    {
        return Err(decode_error(
            "artifact header does not match declared columns",
        ));
    }
    let mut components: Vec<_> = options
        .columns
        .iter()
        .map(|c| Component {
            name: c.name.clone(),
            shape: Shape::Vector,
            values: Values::empty(c.data_type),
            valid: Vec::new(),
        })
        .collect();
    let mut row = 0;
    while let Some(record) = records.next()? {
        let values = fields(record, options.delimiter)?;
        if values.len() != components.len() {
            return Err(decode_error("data record has the wrong number of fields"));
        }
        for (component, value) in components.iter_mut().zip(values) {
            let valid = !missing.contains(value.as_str());
            push_value(&mut component.values, &value, valid, false).map_err(|e| {
                decode_error(format!(
                    "{e} at row {}, column '{}'",
                    row + 1,
                    component.name
                ))
            })?;
            component.valid.push(valid);
        }
        row += 1;
        if row % 1024 == 0 {
            control.checkpoint()?;
        }
    }
    control.checkpoint()?;
    Ok(components)
}

/// Decode the strict LIBSVM/SVMLight subset into a CSR matrix and response.
pub fn decode_libsvm<R: BufRead>(reader: R, options: &LibsvmOptions) -> Result<Vec<Component>> {
    decode_libsvm_with_control(reader, options, &mut || Ok(()))
}

/// Decode LIBSVM with cancellation checkpoints between record batches.
pub fn decode_libsvm_with_control<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    control.checkpoint()?;
    if options.feature_count == 0
        || options.feature_count > (1_u64 << 53) - 1
        || options.target_name.is_empty()
        || options.target_name == "features"
    {
        return Err(unsupported("invalid LIBSVM recipe"));
    }
    let mut records = Records::new(reader);
    let mut row_offsets = vec![0];
    let mut column_indices = Vec::new();
    let mut values = Vec::new();
    let mut labels = Values::empty(match options.label_type {
        LabelType::Int64 => DataType::Int64,
        LabelType::Float64 => DataType::Float64,
    });
    while let Some(record) = records.next()? {
        if record.is_empty() || record.starts_with([' ', '\t']) {
            return Err(decode_error(
                "LIBSVM records must be nonblank without leading whitespace",
            ));
        }
        let mut fields = record.split([' ', '\t']).filter(|s| !s.is_empty());
        let label = fields
            .next()
            .ok_or_else(|| decode_error("missing LIBSVM label"))?;
        push_value(&mut labels, label, true, true)
            .map_err(|e| decode_error(format!("invalid LIBSVM label: {e}")))?;
        let mut previous = 0;
        for field in fields {
            let (index, value) = field
                .split_once(':')
                .ok_or_else(|| decode_error("invalid feature token"))?;
            if !unsigned_decimal(index.as_bytes()) {
                return Err(decode_error("invalid feature index"));
            }
            let index: u64 = index
                .parse()
                .map_err(|_| decode_error("feature index is out of range"))?;
            if index == 0 || index > options.feature_count {
                return Err(decode_error("feature index is out of range"));
            }
            if index == previous {
                return Err(decode_error("duplicate feature index"));
            }
            if index < previous {
                return Err(decode_error("feature indices must be strictly increasing"));
            }
            let value = parse_binary64(value, true)
                .map_err(|e| decode_error(format!("invalid feature value: {e}")))?;
            if value == 0.0 {
                return Err(decode_error("stored sparse zero is invalid"));
            }
            column_indices.push(index - 1);
            values.push(value);
            previous = index;
        }
        row_offsets.push(values.len() as u64);
        if labels.len() % 1024 == 0 {
            control.checkpoint()?;
        }
    }
    control.checkpoint()?;
    let rows = labels.len();
    Ok(vec![
        Component {
            name: "features".into(),
            shape: Shape::Sparse {
                rows: rows as u64,
                columns: options.feature_count,
                row_offsets,
                column_indices,
            },
            values: Values::Float64(values),
            valid: Vec::new(),
        },
        Component {
            name: options.target_name.clone(),
            shape: Shape::Vector,
            values: labels,
            valid: vec![true; rows],
        },
    ])
}

/// Decode train and test independently and retain decoder-defined split order.
pub fn decode_libsvm_split<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
) -> Result<Vec<Component>> {
    decode_libsvm_split_with_control(train, test, options, &mut || Ok(()))
}

/// Decode train and test independently with cancellation checkpoints.
pub fn decode_libsvm_split_with_control<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    let mut components = decode_libsvm_with_control(train, options, control)?;
    for component in &mut components {
        component.name = format!("train_{}", component.name);
    }
    let mut test = decode_libsvm_with_control(test, options, control)?;
    for component in &mut test {
        component.name = format!("test_{}", component.name);
    }
    components.extend(test);
    Ok(components)
}
