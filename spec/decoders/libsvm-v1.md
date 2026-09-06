# LIBSVM and SVMLight Decoder Version 1

This document is normative for the strict common LIBSVM/SVMLight subset decoded
by `libsvm` version `1`. Unknown or omitted options are errors.

## Recipe

- `index_base` is `1`.
- `feature_count` is a positive integer no greater than `2^53 - 1`.
- `duplicate_features` is `error`.
- `label_type` is `int64` or `float64`.
- `row_order` is `source`.
- `target_name` is nonempty and distinct from `features`.

The single-artifact representation has one input named `data`. It produces a
`float64` CSR matrix named `features`, followed by a fully valid vector with the
declared target name and label type. Omitted features are structural zeros.

The `libsvm-split` version `1` assembly applies the same parser independently to
inputs `train` and `test`, in that order. It produces `train_features`,
`train_<target_name>`, `test_features`, and `test_<target_name>` in that order;
it never concatenates or discards a split.

## Record grammar

The artifact is UTF-8 without a byte-order mark. Records use LF or CRLF, and the
final terminator may be omitted. An empty artifact produces zero rows. Blank
records and leading ASCII whitespace are invalid. Fields are separated by one
or more ASCII spaces or tabs; trailing separators are allowed. Unicode
whitespace, comments, and SVMLight `qid` fields are unsupported.

Each record contains a label followed by zero or more `index:value` fields.
Indices use `(0|[1-9][0-9]*)`, fall within `1..feature_count`, and strictly
increase. Duplicate and out-of-order indices are errors.

`int64` labels use `[+-]?(0|[1-9][0-9]*)` within the signed 64-bit range. Float
labels and feature values use
`[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`, rounded to binary64 using
round-to-nearest, ties-to-even. Overflow and non-finite results are invalid.
Feature values that round to positive or negative zero are invalid because
canonical-form version 1 forbids stored sparse zeros.
