# Provisional Delimited Text Decoder Version 1

This document specifies only the slice 0A subset. Unsupported options must
produce an unsupported-decoder error rather than fall back to library defaults.

## Supported recipe

- UTF-8 encoding without a byte-order mark;
- a one-character comma delimiter;
- a required header row;
- double-quote quoting with doubled-quote escaping;
- source row order;
- exact, ordered column names and logical types from the manifest; and
- exact missing-token matching after CSV unquoting and before type conversion.

Rows must have exactly the declared number of fields, and the decoded header
must equal the declared names. Fields are never trimmed.

## Lexical conversion

- `int64` accepts `-?(0|[1-9][0-9]*)` within the signed 64-bit range.
- `float64` accepts
  `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?` and must produce a finite
  binary64 value. Slice 0A rejects overflow and non-finite spellings.
- `bool` accepts only `true` and `false`.
- `string` preserves the decoded UTF-8 value exactly.

The decoder produces an ordered logical vector per column with a separate
validity mask. It validates the component names, types, and lengths in `expect`
before materializing a pandas data frame.
