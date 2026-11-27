use std::borrow::Cow;
use std::collections::{HashMap, HashSet};
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

/// Column and field options shared by the delimited-text recipes.
#[derive(Clone, Debug)]
pub struct DelimitedOptions {
    /// Comma or horizontal tab.
    pub delimiter: u8,
    /// Ordered, uniquely named columns.
    pub columns: Vec<Column>,
    /// Exact tokens matched after unquoting and before lexical conversion.
    pub missing_values: Vec<String>,
}

/// Physical layout for a version 3 delimited-text recipe.
#[derive(Clone, Copy, Debug)]
pub struct DelimitedLayout {
    /// Number of leading physical lines to discard before reading the table.
    pub skip_lines: u32,
    /// Whether the first remaining record must match the declared column names.
    pub header: bool,
}

impl Default for DelimitedLayout {
    fn default() -> Self {
        Self {
            skip_lines: 0,
            header: true,
        }
    }
}

/// LIBSVM response type.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LabelType {
    /// Exact signed integers.
    Int64,
    /// Finite binary64 values.
    Float64,
}

/// The configurable parts shared by LIBSVM recipes 1 and 2.
/// Input indices are one-based and duplicates are errors.
#[derive(Clone, Debug)]
pub struct LibsvmOptions {
    /// Declared feature count, at most `2^53 - 1`.
    pub feature_count: u64,
    /// Response type.
    pub label_type: LabelType,
    /// Response component name, distinct from `features`.
    pub target_name: String,
}

/// Numeric compatibility choices for existing language clients.
#[derive(Clone, Copy, Debug, Default)]
pub struct DecodeOptions {
    /// Reject a nonzero decimal that rounds to zero, as Julia's tryparse does.
    /// Subnormal values that remain nonzero are still accepted.
    pub reject_float_underflow: bool,
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

fn feature_index(text: &str) -> Result<u64> {
    let digits = text.as_bytes();
    if digits.is_empty() || (digits.len() > 1 && digits[0] == b'0') {
        return Err(decode_error("invalid feature index"));
    }
    // Every 19-digit decimal fits in u64, and recipes cap indices at 2^53 - 1.
    // Check longer tokens for syntax so malformed indices retain their diagnostic.
    if digits.len() > 19 {
        return Err(decode_error(if unsigned_decimal(digits) {
            "feature index is out of range"
        } else {
            "invalid feature index"
        }));
    }
    let mut index = 0;
    for &byte in digits {
        let digit = byte.wrapping_sub(b'0');
        if digit > 9 {
            return Err(decode_error("invalid feature index"));
        }
        index = index * 10 + u64::from(digit);
    }
    Ok(index)
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
    parse_binary64_with_options(value, allow_plus, DecodeOptions::default())
}

#[inline]
fn parse_binary64_with_options(
    value: &str,
    allow_plus: bool,
    compatibility: DecodeOptions,
) -> Result<f64> {
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
    if compatibility.reject_float_underflow
        && parsed == 0.0
        && value
            .split(['e', 'E'])
            .next()
            .unwrap_or("")
            .bytes()
            .any(|b| matches!(b, b'1'..=b'9'))
    {
        return Err(decode_error("float64 value underflows to zero"));
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
    fn read_next(&mut self) -> Result<bool> {
        self.buffer.clear();
        if self.reader.read_until(b'\n', &mut self.buffer)? == 0 {
            return Ok(false);
        }
        self.number += 1;
        Ok(true)
    }

    fn next(&mut self) -> Result<Option<&str>> {
        if !self.read_next()? {
            return Ok(None);
        }
        record_text::<false>(&self.buffer, self.number).map(|(text, _)| Some(text))
    }

    fn for_each(&mut self, mut decode: impl FnMut(&str, bool) -> Result<()>) -> Result<()> {
        loop {
            let buffer = match self.reader.fill_buf() {
                Ok([]) => return Ok(()),
                Ok(buffer) => buffer,
                Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(error) => return Err(error.into()),
            };

            // Borrow complete records and keep a scratch buffer for lines
            // that cross a buffer boundary.
            let mut start = 0;
            for end in memchr::memchr_iter(b'\n', buffer) {
                self.number += 1;
                let result = record_text::<true>(&buffer[start..=end], self.number)
                    .and_then(|(text, quoted)| decode(text, quoted));
                start = end + 1;
                if let Err(error) = result {
                    self.reader.consume(start);
                    return Err(error);
                }
            }
            let has_partial_record = start < buffer.len();
            self.reader.consume(start);
            if has_partial_record && self.read_next()? {
                let (text, quoted) = record_text::<true>(&self.buffer, self.number)?;
                decode(text, quoted)?;
            }
        }
    }
}

#[inline]
fn record_text<const FIND_QUOTES: bool>(bytes: &[u8], number: usize) -> Result<(&str, bool)> {
    let record = match bytes.strip_suffix(b"\n") {
        Some(line) => line.strip_suffix(b"\r").unwrap_or(line),
        None => bytes,
    };
    let (quoted, has_bare_cr) = if FIND_QUOTES {
        match memchr::memchr2(b'\r', b'"', record) {
            None => (false, false),
            Some(index) if record[index] == b'"' => (true, record[index + 1..].contains(&b'\r')),
            Some(_) => (false, true),
        }
    } else {
        (false, record.contains(&b'\r'))
    };
    if has_bare_cr {
        return Err(decode_error(format!(
            "bare carriage return at record {number}"
        )));
    }
    if number == 1 && record.starts_with(&[0xef, 0xbb, 0xbf]) {
        return Err(decode_error("artifact has a UTF-8 byte-order mark"));
    }
    std::str::from_utf8(record)
        .map(|text| (text, quoted))
        .map_err(|_| decode_error(format!("invalid UTF-8 at record {number}")))
}

fn fields(record: &str, delimiter: u8, width: usize) -> Result<Vec<Cow<'_, str>>> {
    let bytes = record.as_bytes();
    let mut fields = Vec::with_capacity(width);
    let mut i = 0;
    loop {
        // ASCII quotes and delimiters are always UTF-8 character boundaries.
        let value = if bytes.get(i) == Some(&b'"') {
            i += 1;
            let start = i;
            let mut escaped = false;
            loop {
                match bytes.get(i) {
                    None => return Err(decode_error("unterminated quoted field")),
                    Some(b'"') if bytes.get(i + 1) == Some(&b'"') => {
                        escaped = true;
                        i += 2;
                    }
                    Some(b'"') => break,
                    Some(_) => i += 1,
                }
            }
            let text = &record[start..i];
            i += 1;
            if i < bytes.len() && bytes[i] != delimiter {
                return Err(decode_error("closing quote has a trailing suffix"));
            }
            if escaped {
                Cow::Owned(text.replace("\"\"", "\""))
            } else {
                Cow::Borrowed(text)
            }
        } else {
            let start = i;
            while i < bytes.len() && bytes[i] != delimiter {
                if bytes[i] == b'"' {
                    return Err(decode_error("quote inside unquoted field"));
                }
                i += 1;
            }
            Cow::Borrowed(&record[start..i])
        };
        fields.push(value);
        if i == bytes.len() {
            break;
        }
        i += 1;
    }
    Ok(fields)
}

#[inline]
fn push_value(
    values: &mut Values,
    text: &str,
    valid: bool,
    allow_plus: bool,
    compatibility: DecodeOptions,
) -> Result<()> {
    match values {
        Values::Float64(v) => v.push(if valid {
            parse_binary64_with_options(text, allow_plus, compatibility)?
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

#[inline]
fn decode_delimited_row(
    components: &mut [Component],
    mut fields: impl Iterator<Item = impl AsRef<str>>,
    missing: &HashSet<&str>,
    compatibility: DecodeOptions,
    row: usize,
) -> Result<()> {
    let width_error = || decode_error("data record has the wrong number of fields");
    let mut components = components.iter_mut();
    while let Some(component) = components.next() {
        let field = fields.next().ok_or_else(width_error)?;
        let text = field.as_ref();
        let valid = missing.is_empty() || !missing.contains(text);
        if let Err(error) = push_value(&mut component.values, text, valid, false, compatibility) {
            // Report a malformed width before any invalid value in the row.
            if fields.count() != components.len() {
                return Err(width_error());
            }
            return Err(decode_error(format!(
                "{error} at row {}, column '{}'",
                row + 1,
                component.name
            )));
        }
        if !missing.is_empty() {
            component.valid.push(valid);
        }
    }
    if fields.next().is_some() {
        return Err(width_error());
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
    decode_delimited_impl(
        reader,
        options,
        DelimitedLayout::default(),
        DecodeOptions::default(),
        control,
    )
}

/// Decode with explicit numeric compatibility for an existing client.
pub fn decode_delimited_with_options<R: BufRead>(
    reader: R,
    options: &DelimitedOptions,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_delimited_with_layout(reader, options, DelimitedLayout::default(), compatibility)
}

/// Decode delimited text with an explicit version 3 layout.
pub fn decode_delimited_with_layout<R: BufRead>(
    reader: R,
    options: &DelimitedOptions,
    layout: DelimitedLayout,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_delimited_impl(reader, options, layout, compatibility, &mut || Ok(()))
}

fn decode_delimited_impl<R: BufRead>(
    reader: R,
    options: &DelimitedOptions,
    layout: DelimitedLayout,
    compatibility: DecodeOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    control.checkpoint()?;
    let mut names = HashSet::new();
    if !matches!(options.delimiter, b',' | b';' | b'\t')
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
    for _ in 0..layout.skip_lines {
        records
            .next()?
            .ok_or_else(|| decode_error("delimited artifact ended in the preamble"))?;
    }
    if layout.header {
        let header = fields(
            records
                .next()?
                .ok_or_else(|| decode_error("delimited artifact is empty"))?,
            options.delimiter,
            options.columns.len(),
        )?;
        if header
            .iter()
            .map(AsRef::as_ref)
            .ne(options.columns.iter().map(|c| c.name.as_str()))
        {
            return Err(decode_error(
                "artifact header does not match declared columns",
            ));
        }
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
    records.for_each(|record, quoted| {
        if quoted {
            let values = fields(record, options.delimiter, components.len())?;
            decode_delimited_row(
                &mut components,
                values.into_iter(),
                &missing,
                compatibility,
                row,
            )?;
        } else {
            // The ASCII delimiter always falls on a UTF-8 character boundary.
            let mut remaining = Some(record);
            let values = std::iter::from_fn(|| {
                let text = remaining.take()?;
                match memchr::memchr(options.delimiter, text.as_bytes()) {
                    Some(end) => {
                        remaining = Some(&text[end + 1..]);
                        Some(&text[..end])
                    }
                    None => Some(text),
                }
            });
            decode_delimited_row(&mut components, values, &missing, compatibility, row)?;
        }
        row += 1;
        if row % 1024 == 0 {
            control.checkpoint()?;
        }
        Ok(())
    })?;
    if missing.is_empty() {
        for component in &mut components {
            component.valid.resize(row, true);
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
    decode_libsvm_version_with_control(reader, options, 1, control)
}

/// Decode with explicit numeric compatibility for an existing client.
pub fn decode_libsvm_with_options<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_libsvm_version_with_options(reader, options, 1, compatibility)
}

/// Decode a declared LIBSVM version with cancellation checkpoints.
pub fn decode_libsvm_version_with_control<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    version: u32,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    decode_libsvm_impl(
        reader,
        options,
        version,
        DecodeOptions::default(),
        None,
        control,
    )
}

/// Decode a declared LIBSVM version with numeric compatibility options.
pub fn decode_libsvm_version_with_options<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    version: u32,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_libsvm_impl(
        reader,
        options,
        version,
        compatibility,
        None,
        &mut || Ok(()),
    )
}

/// Decode a ranking artifact and retain each row’s query ID.
pub fn decode_svmlight_ranking_with_control<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    index_base: u64,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    decode_libsvm_impl(
        reader,
        options,
        2,
        DecodeOptions::default(),
        Some(index_base),
        control,
    )
}

fn decode_libsvm_impl<R: BufRead>(
    reader: R,
    options: &LibsvmOptions,
    version: u32,
    compatibility: DecodeOptions,
    ranking_base: Option<u64>,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    control.checkpoint()?;
    if !matches!(version, 1 | 2) {
        return Err(unsupported("unsupported LIBSVM version"));
    }
    let index_base = ranking_base.unwrap_or(1);
    if index_base > 1
        || options.feature_count == 0
        || options.feature_count > (1_u64 << 53) - 1
        || options.target_name.is_empty()
        || options.target_name == "features"
        || (ranking_base.is_some() && options.target_name == "query_id")
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
    let mut query_ids = Vec::new();
    while let Some(record) = records.next()? {
        let record = if ranking_base.is_some() {
            if record.trim_start_matches([' ', '\t']).starts_with('#') {
                continue;
            }
            record.split_once('#').map_or(record, |(data, _)| data)
        } else {
            record
        };
        if record.is_empty() || record.starts_with([' ', '\t']) {
            return Err(decode_error(
                "LIBSVM records must be nonblank without leading whitespace",
            ));
        }
        // ASCII separators fall on UTF-8 character boundaries.
        let mut offset = 0;
        let mut fields = record
            .as_bytes()
            .split(|byte| matches!(byte, b' ' | b'\t'))
            .map(|field| {
                let end = offset + field.len();
                let token = &record[offset..end];
                offset = end + 1;
                token
            })
            .filter(|field| !field.is_empty());
        let label = fields
            .next()
            .ok_or_else(|| decode_error("missing LIBSVM label"))?;
        push_value(&mut labels, label, true, true, compatibility)
            .map_err(|e| decode_error(format!("invalid LIBSVM label: {e}")))?;
        if ranking_base.is_some() {
            let qid = fields
                .next()
                .and_then(|field| field.strip_prefix("qid:"))
                .ok_or_else(|| decode_error("missing ranking query ID"))?;
            if !unsigned_decimal(qid.as_bytes()) {
                return Err(decode_error("invalid ranking query ID"));
            }
            query_ids.push(
                qid.parse::<i64>()
                    .map_err(|_| decode_error("query ID exceeds int64"))?,
            );
        }
        libsvm_features(
            fields,
            options.feature_count,
            version,
            index_base,
            compatibility,
            &mut column_indices,
            &mut values,
        )?;
        row_offsets.push(values.len() as u64);
        if labels.len() % 1024 == 0 {
            control.checkpoint()?;
        }
    }
    control.checkpoint()?;
    let rows = labels.len();
    let mut components = vec![
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
    ];
    if ranking_base.is_some() {
        components.push(Component {
            name: "query_id".into(),
            shape: Shape::Vector,
            values: Values::Int64(query_ids),
            valid: vec![true; rows],
        });
    }
    Ok(components)
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
    decode_libsvm_split_version_with_control(train, test, options, 1, control)
}

/// Decode a split with explicit numeric compatibility for an existing client.
pub fn decode_libsvm_split_with_options<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_libsvm_split_version_with_options(train, test, options, 1, compatibility)
}

/// Decode both splits with the declared LIBSVM version and cancellation.
pub fn decode_libsvm_split_version_with_control<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
    version: u32,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    decode_libsvm_split_impl(
        train,
        test,
        options,
        version,
        DecodeOptions::default(),
        control,
    )
}

/// Decode both splits with the declared LIBSVM version and numeric compatibility.
pub fn decode_libsvm_split_version_with_options<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
    version: u32,
    compatibility: DecodeOptions,
) -> Result<Vec<Component>> {
    decode_libsvm_split_impl(train, test, options, version, compatibility, &mut || Ok(()))
}

fn decode_libsvm_split_impl<R: BufRead, S: BufRead>(
    train: R,
    test: S,
    options: &LibsvmOptions,
    version: u32,
    compatibility: DecodeOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    let mut components = decode_libsvm_impl(train, options, version, compatibility, None, control)?;
    for component in &mut components {
        component.name = format!("train_{}", component.name);
    }
    let mut test = decode_libsvm_impl(test, options, version, compatibility, None, control)?;
    for component in &mut test {
        component.name = format!("test_{}", component.name);
    }
    components.extend(test);
    Ok(components)
}

fn libsvm_features<'a>(
    fields: impl Iterator<Item = &'a str>,
    feature_count: u64,
    version: u32,
    index_base: u64,
    compatibility: DecodeOptions,
    column_indices: &mut Vec<u64>,
    values: &mut Vec<f64>,
) -> Result<()> {
    let mut previous = None;
    for field in fields {
        let (index, value) = field
            .split_once(':')
            .ok_or_else(|| decode_error("invalid feature token"))?;
        let index = feature_index(index)?;
        if index < index_base || index - index_base >= feature_count {
            return Err(decode_error("feature index is out of range"));
        }
        if Some(index) == previous {
            return Err(decode_error("duplicate feature index"));
        }
        if Some(index) < previous {
            return Err(decode_error("feature indices must be strictly increasing"));
        }
        let value = parse_binary64_with_options(
            value,
            true,
            if version == 2 {
                DecodeOptions::default()
            } else {
                compatibility
            },
        )
        .map_err(|e| decode_error(format!("invalid feature value: {e}")))?;
        previous = Some(index);
        if value == 0.0 {
            if version == 1 {
                return Err(decode_error("stored sparse zero is invalid"));
            }
            continue;
        }
        column_indices.push(index - index_base);
        values.push(value);
    }
    Ok(())
}

/// Options for multilabel LIBSVM with a declared class range.
pub struct LibsvmMultilabelOptions {
    /// Number of feature columns.
    pub feature_count: u64,
    /// Number of response columns.
    pub label_count: u64,
    /// First source label, zero or one.
    pub label_index_base: u64,
    /// Name of the response component.
    pub target_name: String,
}

/// Decode multilabel LIBSVM into feature and indicator matrices.
pub fn decode_libsvm_multilabel_with_control<R: BufRead>(
    reader: R,
    options: &LibsvmMultilabelOptions,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    control.checkpoint()?;
    let limit = (1_u64 << 53) - 1;
    if !(1..=limit).contains(&options.feature_count)
        || !(1..=limit).contains(&options.label_count)
        || options.label_index_base > 1
        || options.target_name.is_empty()
        || options.target_name == "features"
    {
        return Err(unsupported("invalid multilabel LIBSVM recipe"));
    }
    let mut records = Records::new(reader);
    let (mut feature_offsets, mut label_offsets) = (vec![0], vec![0]);
    let (mut feature_indices, mut label_indices, mut values) = (Vec::new(), Vec::new(), Vec::new());
    while let Some(record) = records.next()? {
        let mut fields = record
            .split([' ', '\t'])
            .filter(|field| !field.is_empty())
            .peekable();
        let first = *fields
            .peek()
            .ok_or_else(|| decode_error("blank LIBSVM record"))?;
        if !first.contains(':') {
            if record.starts_with([' ', '\t']) {
                return Err(decode_error("leading whitespace before LIBSVM labels"));
            }
            fields.next();
            let start = label_indices.len();
            for token in first.split(',') {
                let label =
                    feature_index(token).map_err(|_| decode_error("invalid LIBSVM label ID"))?;
                let column = label
                    .checked_sub(options.label_index_base)
                    .filter(|&column| column < options.label_count)
                    .ok_or_else(|| decode_error("LIBSVM label ID is out of range"))?;
                label_indices.push(column);
            }
            let row = &mut label_indices[start..];
            row.sort_unstable();
            if row.windows(2).any(|pair| pair[0] == pair[1]) {
                return Err(decode_error("duplicate LIBSVM label ID"));
            }
        }
        libsvm_features(
            fields,
            options.feature_count,
            2,
            1,
            DecodeOptions::default(),
            &mut feature_indices,
            &mut values,
        )?;
        feature_offsets.push(values.len() as u64);
        label_offsets.push(label_indices.len() as u64);
        if (feature_offsets.len() - 1) % 1024 == 0 {
            control.checkpoint()?;
        }
    }
    control.checkpoint()?;
    let rows = (feature_offsets.len() - 1) as u64;
    let matrix = |name, columns, row_offsets, column_indices, values| Component {
        name,
        shape: Shape::Sparse {
            rows,
            columns,
            row_offsets,
            column_indices,
        },
        values: Values::Float64(values),
        valid: Vec::new(),
    };
    let indicators = vec![1.0; label_indices.len()];
    Ok(vec![
        matrix(
            "features".into(),
            options.feature_count,
            feature_offsets,
            feature_indices,
            values,
        ),
        matrix(
            options.target_name.clone(),
            options.label_count,
            label_offsets,
            label_indices,
            indicators,
        ),
    ])
}

/// Join a label assignment file to ordered training and test vector shards.
///
/// Inputs contain the assignments, then the training shards, then the test
/// shards. Document IDs are positive integers and label codes are assigned
/// zero-based columns in lexicographic order.
pub fn decode_sparse_label_join<R: BufRead>(
    mut inputs: Vec<R>,
    train_shards: usize,
    feature_count: u64,
    label_count: u64,
    control: &mut impl Control,
) -> Result<Vec<Component>> {
    let limit = (1_u64 << 53) - 1;
    if !(1..=limit).contains(&feature_count)
        || !(1..=limit).contains(&label_count)
        || !(1..inputs.len().saturating_sub(1)).contains(&train_shards)
    {
        return Err(unsupported("invalid sparse label join recipe"));
    }
    control.checkpoint()?;
    let mut codes = HashMap::<String, usize>::new();
    let mut assignments = HashMap::<i64, Vec<usize>>::new();
    let test = inputs.split_off(1 + train_shards);
    let mut records = Records::new(inputs.remove(0));
    let mut row = 0;
    records.for_each(|record, _| {
        let mut fields = record.split_ascii_whitespace();
        let (Some(code), Some(document), Some("1"), None) =
            (fields.next(), fields.next(), fields.next(), fields.next())
        else {
            return Err(decode_error("invalid label assignment"));
        };
        if !code.bytes().all(|byte| byte.is_ascii_alphanumeric()) {
            return Err(decode_error("invalid label code"));
        }
        let document = sparse_document_id(document)?;
        let code_index = if let Some(&index) = codes.get(code) {
            index
        } else {
            let index = codes.len();
            codes.insert(code.to_owned(), index);
            index
        };
        assignments.entry(document).or_default().push(code_index);
        row += 1;
        if row % 1024 == 0 {
            control.checkpoint()?;
        }
        Ok(())
    })?;
    if codes.len() as u64 != label_count {
        return Err(decode_error("label count disagrees with the recipe"));
    }
    let mut ordered_codes: Vec<_> = codes.into_iter().collect();
    ordered_codes.sort_unstable();
    let mut label_indices = vec![0; ordered_codes.len()];
    for (column, (_, index)) in ordered_codes.iter().enumerate() {
        label_indices[*index] = column as u64;
    }

    let mut components = Vec::new();
    for (split, readers) in [("train", inputs), ("test", test)] {
        let mut feature_offsets = vec![0];
        let mut response_offsets = vec![0];
        let mut indices = Vec::new();
        let mut labels = Vec::new();
        let mut weights = Vec::new();
        let mut ids = Vec::new();
        for reader in readers {
            Records::new(reader).for_each(|record, _| {
                let mut fields = record.split_ascii_whitespace();
                let document = sparse_document_id(
                    fields
                        .next()
                        .ok_or_else(|| decode_error("blank ID-prefixed vector record"))?,
                )?;
                let topics = assignments.remove(&document).ok_or_else(|| {
                    decode_error(format!("document {document} is repeated or has no labels"))
                })?;
                let start = labels.len();
                labels.extend(topics.into_iter().map(|topic| label_indices[topic]));
                labels[start..].sort_unstable();
                if labels[start..].windows(2).any(|pair| pair[0] == pair[1]) {
                    return Err(decode_error(format!(
                        "duplicate label for document {document}"
                    )));
                }
                libsvm_features(
                    fields,
                    feature_count,
                    2,
                    1,
                    DecodeOptions::default(),
                    &mut indices,
                    &mut weights,
                )?;
                feature_offsets.push(weights.len() as u64);
                response_offsets.push(labels.len() as u64);
                ids.push(document);
                if ids.len() % 1024 == 0 {
                    control.checkpoint()?;
                }
                Ok(())
            })?;
        }
        let rows = ids.len() as u64;
        let matrix = |name, columns, row_offsets, column_indices, values| Component {
            name: format!("{split}/{name}"),
            shape: Shape::Sparse {
                rows,
                columns,
                row_offsets,
                column_indices,
            },
            values: Values::Float64(values),
            valid: Vec::new(),
        };
        let indicators = vec![1.0; labels.len()];
        components.extend([
            matrix("features", feature_count, feature_offsets, indices, weights),
            matrix(
                "response",
                label_count,
                response_offsets,
                labels,
                indicators,
            ),
            Component {
                name: format!("{split}/document_id"),
                shape: Shape::Vector,
                valid: vec![true; ids.len()],
                values: Values::Int64(ids),
            },
        ]);
    }
    if !assignments.is_empty() {
        return Err(decode_error("label assignments reference absent documents"));
    }
    control.checkpoint()?;
    components.push(Component {
        name: "label_codes".into(),
        shape: Shape::Vector,
        valid: vec![true; ordered_codes.len()],
        values: Values::String(ordered_codes.into_iter().map(|(code, _)| code).collect()),
    });
    Ok(components)
}

fn sparse_document_id(token: &str) -> Result<i64> {
    feature_index(token)
        .ok()
        .and_then(|value| i64::try_from(value).ok())
        .filter(|&value| value > 0)
        .ok_or_else(|| decode_error("invalid document ID"))
}
