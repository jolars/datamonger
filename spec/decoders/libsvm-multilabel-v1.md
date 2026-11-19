# Multilabel LIBSVM decoder version 1

Manifest schema 6 allows `libsvm-multilabel` version 1 with one input named
`data`, including as a child of `named-splits` version 1. Use the LIBSVM v2
feature grammar and options, replacing `label_type` with `label_count` and
`label_index_base`. The count is between 1 and 2^53 - 1. The label base is 0 or
1 independently of the one-based feature indices.

A labeled row begins with an unsigned decimal ID or a comma-separated list
of IDs. The decimal grammar is `0|[1-9][0-9]*`. Every ID must be in the
declared range and appear at most once per row. The decoder sorts labels by
column. A row whose first non-whitespace field is a feature token has an empty
label set. Only feature-only rows may start with ASCII spaces or tabs. Blank
records, empty comma elements, and malformed features are decode errors.
An empty artifact has zero rows and retains both declared widths.

The decoder emits `features` followed by the declared target, using float64 CSR
for both. Label ID `k` corresponds to zero-based column
`k - label_index_base`. Assigned classes have a stored value of 1. Absent
classes have structural zeros. Row order and split membership follow the
source. Canonical form 1 covers both matrices.

Python and Julia return `MultilabelSparseDataset`. R returns a
`datamonger_multilabel_sparse_dataset`. Each exposes `features`, `response`,
and `label_index_base`. Julia and R use one-based native matrix indexing.
