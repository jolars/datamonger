# Canonical Logical Form Version 1

This document is normative. It defines a verification stream, not a general
storage format. Clients may hash the stream incrementally without retaining it.

All framing integers are unsigned little-endian unless explicitly signed.
Lengths and dimensions must fit their widths. Names are nonempty, unique UTF-8
byte strings with no Unicode normalization.

## Stream header

1. ASCII `DMCF`.
2. Canonical-form version as `uint16`, equal to `1`.
3. Component count as `uint32`.

Components occur in decoder-defined order. Zero components are valid.

## Common tags

- Kind `1`: vector.
- Kind `2`: compressed sparse row matrix.
- Kind `3`: dense matrix.
- Element type `1`: `float64`.
- Element type `2`: `int64`.
- Element type `3`: `string`.
- Element type `4`: `bool`.

Every component begins with its UTF-8 name length as `uint32`, the name bytes,
its one-byte kind tag, one-byte element-type tag, and one-byte rank.

## Vector

A vector has rank `1`, followed by its length as `uint64`, a validity bitmap,
and its values. Bitmap bit `i mod 8` of byte `i div 8` describes element `i`;
one means valid. Unused high bits must be zero.

## Dense matrix

A dense matrix has rank `2`, followed by row and column counts as `uint64`.
The element count is their mathematical product and must fit `uint64`. A
validity bitmap covers elements in row-major order, followed by values in the
same order. Empty dimensions use an empty bitmap and value sequence.

## Sparse matrix

Version 1 supports only `float64` compressed sparse row matrices. Rank `2` is
followed by row count, column count, and stored nonzero count as `uint64`; then
exactly `rows + 1` zero-based row offsets as `uint64`; one zero-based column
index per stored value as `uint64`; and one canonical float word per value.

The first offset is zero, offsets are nondecreasing and at most the nonzero
count, and the final offset equals that count. Column indices are in range and
strictly increase within each row. Sparse matrices have no validity bitmap.
Duplicates, missing values, and stored positive or negative zero are invalid.

## Values

- `float64` is an IEEE 754 binary64 word in little-endian order. Negative zero
  becomes positive zero, and every NaN becomes quiet NaN
  `0x7ff8000000000000`. Invalid dense or vector storage is positive zero.
- `int64` is a signed two's-complement little-endian word. Invalid storage is
  zero.
- `string` is a `uint64` UTF-8 byte length followed by the bytes. An invalid
  string has length zero and no bytes; validity distinguishes it from a valid
  empty string.
- `bool` values are an LSB-first bitmap. Invalid and unused bits are zero.

The validity bitmap always precedes the value area. For dense matrices, all
value encodings use row-major logical order regardless of host layout.

## Verification lifecycle

A verification record identifies this version, digest algorithm `sha256`, and
the lowercase digest of the complete stream. Records are append-only. A client
uses a supported non-revoked record and reports the version and digest used.
An approved erratum may revoke an incorrect record and append a replacement;
it never changes earlier release bytes or dataset identity.
