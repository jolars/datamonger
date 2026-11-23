# Decoders

A representation selects a recipe with `decoder` and `decoder_version`. The
[manifest schemas](schema/) define which recipes are available in each schema
version. The [conformance fixtures](../tests/conformance/) exercise parsing and
logical output across clients.

## Delimited text version 1

`delimited-text` version 1 handles CSV and TSV artifacts. Every listed option is required except `missing_values`, whose
default is an empty array. Unknown options are errors.

### Recipe

- `encoding` is `utf-8`; a byte-order mark is invalid.
- `delimiter` is `,` for a `csv` artifact or one horizontal tab for `tsv`.
- `header` is `true`.
- `quote` is `"` and `escape` is `double`.
- `row_order` is `source`.
- `columns` is a nonempty ordered array of unique, nonempty names and one of
  `float64`, `int64`, `string`, or `bool`.
- `missing_values` is an array of unique strings matched exactly after CSV
  unquoting and before lexical conversion.

The representation has exactly one input named `data`. The input artifact format
and delimiter must agree. Components are ordered exactly as `columns`.

### Record grammar

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

### Lexical conversion

- `int64` accepts `-?(0|[1-9][0-9]*)` in the signed 64-bit range.
- `float64` accepts `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`. The
  mathematical value is rounded to binary64 using round-to-nearest,
  ties-to-even. Overflow and a non-finite result are invalid; underflow and
  signed zero are permitted.
- `bool` accepts only `true` and `false`.
- `string` preserves the decoded Unicode scalar sequence exactly.

Missing tokens bypass conversion and produce invalid logical values with the
canonical zero storage for their type. The decoder validates declared component
names, types, and lengths before exposing a native table.

## Delimited text version 2

Manifest schema 5 adds `delimited-text` version 2, including as a child of
`named-splits` version `1`.

Version 2 follows [version 1](#delimited-text-version-1) and accepts either a comma
(`,`) or a semicolon (`;`) for an artifact with `format: csv`. An artifact with
`format: tsv` requires a horizontal tab. The manifest explicitly declares
the delimiter. The same quoting, escaping, and canonical verification rules
apply with each delimiter.

## Delimited text layout in the Rust core

The core decoder supports two additional layout options, originally documented
as delimited text version 3. The registry manifest schemas do not expose them.

- `skip_lines` is an optional integer from 0 through 4294967295 and defaults
  to 0. Discard exactly this many leading physical lines before parsing the
  table. The discarded lines must follow the encoding and line-ending rules
  but may contain arbitrary text. Reaching the end of input before discarding
  the declared number of lines is an error.
- `header` is a required boolean. If true, the first remaining record must
  match the declared column names. If false, every remaining record is a data
  row and the manifest supplies the column names. A headerless input with no
  remaining records produces zero-length components.

For SNAP road networks such as `roadNet-CA`, use `skip_lines: 4` and
`header: false` with two integer columns. The decoder retains source row
order, including rows with reversed endpoint pairs.

## LIBSVM and SVMLight version 1

This document is normative for the strict common LIBSVM/SVMLight subset decoded
by `libsvm` version `1`. Unknown or omitted options are errors.

### Recipe

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

### Record grammar

The artifact is UTF-8 without a byte-order mark. Records use LF or CRLF, and the
final terminator may be omitted. An empty artifact produces zero rows. Blank
records and leading ASCII whitespace are invalid. Fields are separated by one or
more ASCII spaces or tabs; trailing separators are allowed. Unicode whitespace,
comments, and SVMLight `qid` fields are unsupported.

Each record contains a label followed by zero or more `index:value` fields.
Indices use `(0|[1-9][0-9]*)`, fall within `1..feature_count`, and strictly
increase. Duplicate and out-of-order indices are errors.

`int64` labels use `[+-]?(0|[1-9][0-9]*)` within the signed 64-bit range. Float
labels and feature values use
`[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`, rounded to binary64 using
round-to-nearest, ties-to-even. Overflow and non-finite results are invalid.
Feature values that round to positive or negative zero are invalid because
canonical-form version 1 forbids stored sparse zeros.

## LIBSVM and SVMLight version 2

Manifest schema 5 adds `libsvm` and `libsvm-split` version 2.

Version 2 follows [version 1](#libsvm-and-svmlight-version-1) with one change
to zero-valued feature entries. After parsing and rounding a feature value to binary64, the decoder
omits the entry if its value is positive or negative zero. This includes nonzero
decimal values that underflow to zero. Labels are never omitted.

All input indices, including those belonging to omitted zero entries, must
remain in range and strictly increasing. Duplicate and out-of-order indices
remain errors. The declared feature count, row count, row order, labels, and
train/test boundaries are preserved, including rows containing only zeros. All
other grammar, recipe options, component names, and types match version 1.

Both splits in `libsvm-split` version 2 use the version 2 parser. A
`named-splits` version 1 assembly in schema 5 may select `libsvm` version 2 for
any child independently; the assembly itself remains version 1.

Canonical-form version 1 is unchanged: decoded sparse matrices store no zeros.
An explicit zero and an omitted feature therefore produce identical canonical
bytes. Artifact size and SHA-256 still cover the exact upstream bytes, including
explicit zeros. Omitting zeros is decoder normalization, not a rewrite of the
downloaded artifact or statistical preprocessing.

## Multilabel LIBSVM version 1

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

## SVMLight ranking version 1

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

## Named splits version 1

### Recipe and inputs

`inputs` maps each provider split name to an artifact name. Split names are
nonempty UTF-8 strings, preserved exactly, including case, spaces, and
punctuation. Names must be unique. Do not rename validation data to test data.

`options` contains exactly `splits`, a nonempty ordered array. Each entry has
exactly `name`, `decoder`, `decoder_version`, and `options`. `name` selects the
same-named input. The input keys must equal the set of declared split names;
JSON object key order has no meaning. The array defines split and component
order. Multiple splits may explicitly select the same artifact.

Each child selects `delimited-text` version `1` or `libsvm` version `1` and
supplies that decoder's complete options. Nested assemblies are unsupported. The
artifact format, compression, accepted bytes, row order, logical types,
missingness, and errors follow the selected single-artifact contract. Clients
must dispatch child versions before interpreting their options. Invalid assembly
recipes or unsupported child versions fail as `unsupported-decoder`. Unknown
artifact references remain `unsupported-registry` errors.

Manifest schema version 5 also allows
[delimited-text version 2](#delimited-text-version-2) as a child decoder.
Manifest schema version 6 also allows
[multilabel LIBSVM version 1](#multilabel-libsvm-version-1).
Manifest schema version 7 also allows
[SVMLight ranking version 1](#svmlight-ranking-version-1).

For example, the outline below assembles two labeled sparse inputs and a table
containing only test features. Replace each options placeholder with the
complete child recipe:

```yaml
decoder: named-splits
decoder_version: 1
inputs:
  train: training-artifact
  validation: validation-artifact
  test: test-features-artifact
options:
  splits:
    - name: train
      decoder: libsvm
      decoder_version: 1
      options: <training LIBSVM options>
    - name: validation
      decoder: libsvm
      decoder_version: 1
      options: <validation LIBSVM options>
    - name: test
      decoder: delimited-text
      decoder_version: 1
      options: <test feature column options>
```

### Logical output and verification

Decode each child independently. Preserve every row, its original order, and its
split membership. Do not concatenate, shuffle, rebalance, or discard rows. A
feature-only table has no response component. Do not invent labels, add a column
of missing labels, or require a target column to decode it. Version 1 LIBSVM
continues to require labels; use a delimited feature-only artifact when the
provider has no labels.

The assembly's logical output concatenates the child component sequences in the
declared split order. Qualify each component name as
`escape(split_name)/escape(child_component_name)`, where `escape` replaces `~`
with `~0`, then `/` with `~1`. This escaping is injective and performs no
Unicode normalization. Thus `train/features` and `validation/response` are
ordinary qualified names, and split `Test / α~` and column `signal/~` produce
`Test ~1 α~0/signal~1~0`. Native tables retain the original column names.

Component values, types, dimensions, validity, and sparse structure remain
unchanged. `expect.components` must name the complete qualified sequence in
order and must match each child recipe's shapes and types. Canonical form `1`
encodes that sequence using its existing rules. Names, order, membership, and
the absence of a response therefore participate in decoded verification.
Component or digest mismatches fail as `decoded-integrity`.

Clients return a mapping of exact split names to native table or sparse
datasets, with iteration in recipe order: Python and Julia expose
`DatasetSplits`, and R exposes the named list `datamonger_dataset_splits`.
`data["validation"]` in Python and Julia, or `data[["validation"]]` in R,
selects that provider split. `return_info` wraps this same mapping and records
all consumed artifact digests. Disabling decoded verification does not disable
artifact verification or recipe validation.

### Split tasks

For schema version `4`, classification and regression tasks may declare
feature-only split roles. Every split must declare features, a target, or both,
and at least one split in a supervised task must declare a target. Unsupervised
tasks still require features and forbid targets in every split. Top-level roles
retain the earlier requirements. A `named-splits` task must use split roles
whose keys select declared provider splits. Each role must refer to components
within that same split, using qualified names. Feature-array order remains
semantic. Task metadata never adds, removes, or transforms data.

The shared extension cases in
[`tests/conformance/named-splits.json`](../tests/conformance/named-splits.json)
exercise public client fetching, exact values and membership, feature-only and
empty test tables, provider names, component bytes, malformed recipes, and
verification failures.

## Graph tables and HIF version 1

Manifest and index schema 8 add `graph-tables` and `hif` decoder version 1.
An index may mix manifest versions 1 through 8. Both decoders accept artifact
compression `none`, `gzip`, and `bzip2`.

### Graph tables

Use modality `graph`. The `nodes` and `edges` inputs select CSV or TSV
artifacts. Options contain the boolean `directed` and a complete
[delimited-text version 1 recipe](#delimited-text-version-1) under each input role.

Nodes have a unique, non-null `id` column of type `int64` or `string`.
Edges have non-null `source` and `target` columns of the same type, and both
must refer to node IDs. An optional edge `id` follows the same rules as the
node key. All other columns are attributes. Both tables retain source row and
column order, including isolates, self-loops, and parallel edges.

### HIF

Use modality `hypergraph` and a single `data` input with artifact format
`hif`. Options contain the boolean `directed`, the `node_id` and `edge_id`
types (`int64` or `string`), and column specifications under `nodes`,
`hyperedges`, and `incidences`. Each specification contains a boolean
`weight` and an ordered array of `attributes` with `name` and `type`. Attribute
types are `int64`, `float64`, `string`, and `bool`.

The JSON artifact contains `incidences` and may contain `nodes`, `edges`,
`network-type`, and an object named `metadata`. Network type must match the
recipe and defaults to undirected when absent. Explicit entity records use
`node` or `edge` keys. Incidences use both and retain source order. Explicit
nodes and hyperedges come first in each table, followed by entities inferred
in first incidence order. Entity output keys are named `id`. Incidence output
keys are `node` and `edge`, followed by `direction` for directed hypergraphs.
Directed memberships use `head` or `tail`. Memberships must be unique, including
direction when present.

An enabled top-level `weight` produces a nullable float64 column after the
structural columns. Declared `attrs` follow in recipe order. Missing
attributes and weights are null, including on inferred entities. Attribute
names must be unique within each table and must avoid the table's structural
names and any enabled weight column. Undeclared attributes and weights are
decode errors.

### Verification and client results

Canonical form 1 starts with a length-one, valid boolean vector named
`directed`. The ordered table columns follow, with names prefixed by
`nodes/`, then `edges/` for graphs or `hyperedges/` and `incidences/` for
hypergraphs. Public tables expose the original column names. Turning off
decoded verification still requires verified artifact bytes and valid topology.
