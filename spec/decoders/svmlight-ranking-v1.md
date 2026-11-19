# SVMLight ranking decoder version 1

Manifest schema 7 allows `svmlight-ranking` version 1 with one input named
`data`, including as a child of `named-splits` version 1. Use the LIBSVM v2
recipe, with `index_base` set to 0 or 1 and a target name distinct from
`features` and `query_id`.

Every data row contains a label, exactly one `qid:<id>` field, and zero or more
feature tokens. Query IDs use `0|[1-9][0-9]*` and fit in signed int64. The
decoder preserves IDs and source row order, including repeated and nonmonotone
IDs. Feature indices are strictly increasing and lie in the declared range
from `index_base` through `index_base + feature_count - 1`. LIBSVM v2 numeric
grammar and explicit zero normalization apply.

A hash starts a comment that extends to the end of the record. Comments after
data tokens and comment-only records are allowed. A comment-only record may
start with ASCII spaces or tabs. Other record rules follow LIBSVM v2.

The decoder emits the float64 CSR component `features`, the declared target
vector, and the fully valid int64 vector `query_id`, in that order. These
components use canonical form 1, including ordinary name qualification inside
named splits. Ranking tasks specify `features`, `target`, and `query_id` roles
for each participating split or for a single-artifact dataset.

Python and Julia expose a `RankingSparseDataset`. R exposes a
`datamonger_ranking_sparse_dataset`. Their fields are `features`, `response`,
and `query_id` in matching row order.
