# Preprocessing metadata extension

This extension introduces manifest and index schema version 3. Versions 1 and 2
retain their contracts. Dataset identity, decoder recipes, canonical forms,
selectors, release sources, and catalogs are unchanged.

## Manifest records

The optional top-level `preprocessing` object describes processing already
reflected in the registered artifacts. It has two required stage records:

- `upstream`: processing performed by the original producers or distributing
  collections before Datamonger acquired the data.
- `datamonger`: processing performed during Datamonger's preparation of the
  registered artifacts.

Each stage requires `status`:

- `unknown`: processing has not been established. Omit `steps`.
- `none`: evidence establishes that this stage applies no preprocessing.
  Omit `steps` and supply nonempty `evidence`.
- `documented`: at least one known step is recorded. Supply nonempty `steps`
  and `evidence` arrays. This records known processing, without claiming that
  the history is exhaustive.

Optional `notes` supply nonempty text, including limitations of the available
history. `evidence` is an array of nonempty reference strings, such as provider
URLs, publication references, or repository-relative documentation and recipe
paths. References are descriptive; clients do not retrieve or execute them.
Unknown processing must not be inferred to mean no processing. Missing
`preprocessing` means that neither stage has been recorded.

Each step requires a `kind` identifier and a nonempty `description`. Use
`normalization`, `scaling`, `centering`, `imputation`, `missing-value-removal`,
`feature-selection`, `feature-encoding`, `sample-selection`, `aggregation`,
`response-transformation`, `response-dichotomization`, or `label-mapping` where
applicable. Other identifiers are allowed. Clients must preserve unfamiliar
kinds as descriptive metadata.

An optional `parameters` object maps nonempty names to nonempty strings. Record
methods, affected axes or columns, thresholds, class mappings, and the population
used to fit a transformation when known. Quote numeric and boolean parameters
as strings to preserve their documented precision without changing registry
number serialization. Omit unknown parameters rather than guessing them.

The `steps` array preserves the documented order. Combine operations in one
description if their internal order is unknown. Statistical transformations,
filtering, aggregation, and label changes belong here. Lossless file conversion,
compression, and ordinary manifest-declared decoding do not establish that
statistical preprocessing occurred. `missing_values` remains a decoder option
for recognizing missing tokens; it does not document earlier NA removal.

For example, this hypothetical record describes a prepared binary response:

```yaml
preprocessing:
  upstream:
    status: unknown
  datamonger:
    status: documented
    evidence:
      - curation/example/1/DATASET.md
      - curation/example/1/prepare.py
    steps:
      - kind: missing-value-removal
        description: Exclude observations with a missing response.
        parameters:
          axis: rows
          column: outcome
      - kind: response-dichotomization
        description: Define y as one when outcome is at least seven, otherwise zero.
        parameters:
          input: outcome
          output: y
          threshold: '7'
          predicate: outcome >= threshold
```

Preprocessing records are release-scoped descriptive metadata. Adding or
correcting the description of existing artifacts does not require a new dataset
version. Changing the actual processing, artifact bytes, or decoder recipe does
require a new dataset version under the identity contract. Published release
bytes remain immutable.

When checking an existing release, the builder uses its snapshot's dataset
records after validating the current authoring manifests and checking that the
dataset set and identity-bearing fields still agree. It regenerates defaults,
errata, and selector bytes for comparison with the published outputs. Preparing
a release uses the current authoring metadata and checks it against historical
releases, even when that candidate already has generated outputs. This permits
metadata updates without rewriting older snapshots or concealing changes to a
pending release.

## Registry compatibility

Index version 3 accepts manifest versions 1, 2, and 3. Older index versions keep
their existing manifest limits. The builder emits the highest manifest schema
version selected by the release. Selectors, release sources, and catalogs retain
version 1. Unsupported index and manifest versions remain errors.

## Client behavior

Python, R, and Julia expose `preprocessing` through `data_info()`, `list_data()`,
and fetch metadata requested with `return_info`. Missing metadata is `None`,
`NULL`, or `nothing`. Explicit unknown stages and every recorded step, parameter,
note, and evidence reference are preserved. Metadata describes the same registry
record used for retrieval and requires no additional lookup. The CLI preserves
the field in its dataset metadata output.

Clients reject malformed preprocessing records as unsupported registry metadata.
They must not execute the steps, transform decoded data, infer missing history,
or infer `none` from the absence of a record. Decoder output and verification
digests remain unchanged.
