# Delimited Text Decoder Version 1

This document is normative for CSV and TSV artifacts decoded by
`delimited-text` version `1`. Every listed option is required except
`missing_values`, whose default is an empty array. Unknown options are errors.

## Recipe

- `encoding` is `utf-8`; a byte-order mark is invalid.
- `delimiter` is `,` for a `csv` artifact or one horizontal tab for `tsv`.
- `header` is `true`.
- `quote` is `"` and `escape` is `double`.
- `row_order` is `source`.
- `columns` is a nonempty ordered array of unique, nonempty names and one of
  `float64`, `int64`, `string`, or `bool`.
- `missing_values` is an array of unique strings matched exactly after CSV
  unquoting and before lexical conversion.

The representation has exactly one input named `data`. The input artifact
format and delimiter must agree. Components are ordered exactly as `columns`.

## Record grammar

Records end with LF or CRLF; bare CR is invalid. The final record terminator may
be omitted. Every physical line is one record, including a blank line, which
contains one empty field. Line breaks inside quoted fields are invalid.

A field is quoted or unquoted. An unquoted field extends to the delimiter or
record end and may not contain `"`. A quoted field is enclosed in `"`; an
interior quote is escaped as `""`; the closing quote must be followed
immediately by a delimiter or record end. Fields are never trimmed.

The first record must equal the declared column names exactly. Every following
record must have exactly the declared field count. A header-only artifact
produces zero-length components; an empty artifact is invalid.

## Lexical conversion

- `int64` accepts `-?(0|[1-9][0-9]*)` in the signed 64-bit range.
- `float64` accepts
  `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`. The mathematical value is
  rounded to binary64 using round-to-nearest, ties-to-even. Overflow and a
  non-finite result are invalid; underflow and signed zero are permitted.
- `bool` accepts only `true` and `false`.
- `string` preserves the decoded Unicode scalar sequence exactly.

Missing tokens bypass conversion and produce invalid logical values with the
canonical zero storage for their type. The decoder validates declared component
names, types, and lengths before exposing a native table.
