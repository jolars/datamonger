# Provisional Canonical Form

This document specifies the vector and sparse-matrix encoding used by the
vertical proof.
It is provisional until specification revision 1 is certified independently.

All integers are unsigned little-endian unless stated otherwise. Lengths and
dimensions must fit their declared widths. UTF-8 text is not normalized.

## Stream header

1. The four ASCII bytes `DMCF`.
2. Canonical-form version as `uint16`; slice 0A uses version `1`.
3. Component count as `uint32`.

## Vector component

Components occur in decoder-defined order. A vector is encoded as:

1. Name byte length as `uint32`, followed by the UTF-8 name.
2. Kind tag `1`.
3. Element-type tag: `1` for `float64`, `2` for `int64`, `3` for `string`, or
   `4` for `bool`.
4. Rank `1`.
5. Vector length as `uint64`.
6. A validity bitmap of `ceil(length / 8)` bytes. Bit `i mod 8` of byte
   `i div 8` is one exactly when element `i` is valid. Unused high bits are zero.
7. Values as described below.

The vector encoding above is unchanged from slice 0A.

## Sparse matrix component

Canonical-form version 1 supports float64 sparse matrices in compressed sparse
row order. A sparse matrix is encoded as:

1. Name byte length as `uint32`, followed by the UTF-8 name.
2. Kind tag `2`.
3. Element-type tag `1` for `float64`.
4. Rank `2`.
5. Row count and column count, each as `uint64`.
6. Stored nonzero count as `uint64`.
7. Exactly `rows + 1` zero-based row offsets as `uint64`. The first offset is
   zero, offsets are nondecreasing, and the final offset equals the stored
   nonzero count.
8. One zero-based column index per stored value as `uint64`. Indices are less
   than the column count and strictly increase within each row.
9. One canonical float64 word per stored value.

Sparse matrices have no validity bitmap in version 1. Missing sparse values,
duplicate entries, and stored positive or negative zero are invalid. Empty rows
and empty matrices have their ordinary CSR representation. NaNs and nonzero
finite or infinite values use the float64 normalization below, although a
decoder may define a stricter accepted lexical domain.

## Values

- Vector `float64`: one IEEE 754 binary64 word per element. Negative zero becomes
  positive zero, every NaN becomes `0x7ff8000000000000`, and invalid storage is
  positive zero.
- Vector `int64`: one two's-complement signed 64-bit word per element. Invalid storage
  is zero.
- Vector `string`: each element is a `uint64` UTF-8 byte length followed by those
  bytes. An invalid element has length zero and no bytes; validity distinguishes
  it from a valid empty string.
- Vector `bool`: one LSB-first bitmap with the same length as the validity bitmap. A
  bit is one exactly when the corresponding valid value is true. Invalid and
  unused bits are zero.

Clients hash this stream incrementally. They need not retain the encoded bytes.
