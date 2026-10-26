# LIBSVM and SVMLight Decoder Version 2

This document is normative for `libsvm` version `2` and `libsvm-split`
version `2`. Manifest and index schema version 5 introduce these recipes.
Earlier schema and decoder versions retain their contracts.

Version 2 follows [version 1](libsvm-v1.md) except for zero-valued feature
entries. After parsing and rounding a feature value to binary64, the decoder
omits the entry if its value is positive or negative zero. This includes
nonzero decimal values that underflow to zero. Labels are never omitted.

All input indices, including those belonging to omitted zero entries, must
remain in range and strictly increasing. Duplicate and out-of-order indices
remain errors. The declared feature count, row count, row order, labels,
and train/test boundaries are preserved, including rows containing only zeros.
All other grammar, recipe options, component names, and types match version 1.

Both splits in `libsvm-split` version 2 use the version 2 parser. A
`named-splits` version 1 assembly in schema 5 may select `libsvm` version 2
for any child independently; the assembly itself remains version 1.

Canonical-form version 1 is unchanged: decoded sparse matrices store no
zeros. An explicit zero and an omitted feature therefore produce identical
canonical bytes. Artifact size and SHA-256 still cover the exact upstream
bytes, including explicit zeros. Omitting zeros is decoder normalization,
not a rewrite of the downloaded artifact or statistical preprocessing.

Schema 5 accepts all earlier manifest schemas in an index and preserves the
schema 4 metadata and assembly contracts. Delimited-text and named-splits
remain version 1; schema 5 does not admit version 2 for those decoders.
