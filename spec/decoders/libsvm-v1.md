# Provisional LIBSVM Decoder Version 1

This document specifies only the vertical-proof subset. Unsupported options
must produce an unsupported-decoder error rather than fall back to library
defaults.

## Supported recipe

The representation requires these options:

- `index_base: 1`;
- a positive integer `feature_count`;
- `duplicate_features: error`;
- `label_type` equal to `int64` or `float64`;
- `row_order: source`; and
- a nonempty `target_name` distinct from `features`.

The decoder produces a float64 sparse matrix named `features` and a vector with
the declared target name and label type. Omitted features are structural zeros.

## Record grammar

The artifact is UTF-8 without a byte-order mark. Records use LF or CRLF line
endings; the final record need not end with a line ending. Blank records and
leading whitespace are invalid. Fields are separated by one or more ASCII
spaces or tabs, and trailing ASCII spaces or tabs are allowed. Comments,
SVMLight query identifiers, and Unicode whitespace are unsupported.

Each record contains a label followed by zero or more `index:value` fields.
Feature indices use `(0|[1-9][0-9]*)`, must be within the declared one-based
feature range, and must strictly increase within a record. Duplicate and
out-of-order indices are errors.

`int64` labels use `[+-]?(0|[1-9][0-9]*)` and must fit the signed 64-bit range.
Float labels and feature values use
`[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?` and must produce finite
binary64 values. Explicit positive or negative zero feature values are rejected
because canonical-form version 1 forbids stored sparse zeros.
