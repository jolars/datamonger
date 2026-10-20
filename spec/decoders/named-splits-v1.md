# Named splits decoder version 1

This document is normative for `named-splits` version `1`, available in manifest
and index schema version `4`. It extends the frozen revision 1 profile without
changing its decoders, schemas, canonical form, or error taxonomy.

## Recipe and inputs

`inputs` maps each provider split name to an artifact name. Split names are
nonempty UTF-8 strings, preserved exactly, including case, spaces, and
punctuation. Names must be unique. Do not rename validation data to test data.

`options` contains exactly `splits`, a nonempty ordered array. Each entry has
exactly `name`, `decoder`, `decoder_version`, and `options`. `name` selects the
same-named input. The input keys must equal the set of declared split names;
JSON object key order has no meaning. The array defines split and component
order. Multiple splits may explicitly select the same artifact.

Each child selects `delimited-text` version `1` or `libsvm` version `1` and
supplies that decoder's complete options. Nested assemblies are unsupported.
The artifact format, compression, accepted bytes, row order, logical types,
missingness, and errors follow the selected single-artifact contract. Clients
must dispatch child versions before interpreting their options. Invalid
assembly recipes or unsupported child versions fail as `unsupported-decoder`.
Unknown artifact references remain `unsupported-registry` errors.

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

## Logical output and verification

Decode each child independently. Preserve every row, its original order, and
its split membership. Do not concatenate, shuffle, rebalance, or discard rows.
A feature-only table has no response component. Do not invent labels, add a
column of missing labels, or require a target column to decode it. Version 1
LIBSVM continues to require labels; use a delimited feature-only artifact when
the provider has no labels.

The assembly's logical output concatenates the child component sequences in
the declared split order. Qualify each component name as
`escape(split_name)/escape(child_component_name)`, where `escape` replaces `~`
with `~0`, then `/` with `~1`. This escaping is injective and performs no Unicode
normalization. Thus `train/features` and `validation/response` are ordinary
qualified names, and split `Test / α~` and column `signal/~` produce
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
`data["validation"]` in Python and Julia, or `data[["validation"]]` in R, selects
that provider split. `return_info` wraps this same mapping and records all
consumed artifact digests. Disabling decoded verification does not disable
artifact verification or recipe validation.

## Task metadata and schema version 4

Manifest schema version `4` retains version `3` metadata and earlier decoder
recipes and adds this assembly. Index version `4` accepts manifests of versions
`1` through `4`. Earlier schemas remain unchanged. A changed representation
recipe for a published identity requires a new dataset version under the
existing identity rules, even when it reuses the same artifact bytes.

For schema version `4`, classification and regression tasks may declare
feature-only split roles. Every split must declare features, a target, or both,
and at least one split in a supervised task must declare a target. Unsupervised
tasks still require features and forbid targets in every split. Top-level
roles retain the earlier requirements. A `named-splits` task must use split
roles whose keys select declared provider splits. Each role must refer to
components within that same split, using qualified names. Feature-array order
remains semantic. Task metadata never adds, removes, or transforms data.

The shared extension cases in
[`tests/conformance/named-splits.json`](../../tests/conformance/named-splits.json)
exercise public client fetching, exact values and membership, feature-only and
empty test tables, provider names, component bytes, malformed recipes, and
verification failures. They are additional extension requirements; the frozen
revision 1 conformance cases retain their original meaning.
