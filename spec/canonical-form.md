# Provisional Canonical Form

This document specifies the vector encoding used by vertical-proof slice 0A.
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

Other kind and rank tags are unsupported in slice 0A.

## Values

- `float64`: one IEEE 754 binary64 word per element. Negative zero becomes
  positive zero, every NaN becomes `0x7ff8000000000000`, and invalid storage is
  positive zero.
- `int64`: one two's-complement signed 64-bit word per element. Invalid storage
  is zero.
- `string`: each element is a `uint64` UTF-8 byte length followed by those
  bytes. An invalid element has length zero and no bytes; validity distinguishes
  it from a valid empty string.
- `bool`: one LSB-first bitmap with the same length as the validity bitmap. A
  bit is one exactly when the corresponding valid value is true. Invalid and
  unused bits are zero.

Clients hash this stream incrementally. They need not retain the encoded bytes.
