# Registry releases

Versionary owns registry release PRs, changelogs, tags, and draft GitHub
Releases. The publisher validates the tagged snapshot, attaches `index.json`,
verifies the uploaded digest, and publishes the draft.

- `datasets/` contains dataset manifests.
- `collection.yaml` selects dataset versions and any approved errata for the
  next release.
- `version.txt` is the registry version maintained by Versionary's `simple`
  strategy. Registry versions do not determine dataset or specification
  versions.
- `releases/<version>/` contains immutable generated release sources, indexes,
  and selectors. These are generated and reviewed in the registry release PR.
- `catalog.json` lists the strong selectors for checked-in releases.
- `latest.json` is the selector chosen for scheduled verification. Release
  preparation updates it alongside the catalog; it is not a permanent project
  pin.

The [collection schema](../spec/schema/collection-v1.schema.json) groups
datasets by source and name.

```yaml
schema_version: 1
repository: jolars/datamonger
datasets:
  uci:
    iris:
      versions: ["1"]
```

List every selected version as a quoted string, from oldest to newest. The last
entry is the default for fetches that omit a version. Release preparation loads
each entry from `registry/datasets/<source>/<name>-<version>.yaml` and checks
that the manifest declares the corresponding identity.

Use `feat(registry): ...` for added datasets or capabilities and
`fix(registry): ...` for compatible corrections. Versionary scopes commits by
paths, so those changes must touch the registry's authoring files. Published
identities and indexes remain immutable regardless of the version bump. An
incompatible registry change requires the appropriate major bump and any
separately required dataset or contract versions.

The historical stable release `2026.09` is the Versionary `1.0.0` baseline. Its
existing tag, selector, and index are unchanged. This bookkeeping does not
publish a second registry or create a `1.0.0` selector. Future releases use
semantic identifiers such as `1.1.0` and tags such as `registry-v1.1.0`.

Clients continue to select a registry by its release identifier and index
SHA-256. A new registry release does not automatically release client packages.

## Citations

Use `provenance.citations` to record references in the provider’s order. Each
entry has citation text and can include a role (`dataset`, `paper`, or
`collection`), a note, and a `recommended` flag. Set the flag only when the
provider’s recommendation is known. Preserve instructions to cite multiple
references together in `provenance.citation_instructions`.

Older manifests can use the single `provenance.citation` string. Use only one
of the two citation fields. Clients expose a legacy string as a single
reference with an unspecified role and recommendation. By default,
`cite_data()` returns all references when no flags exist, or only references
flagged `recommended: true` when at least one flag exists. `include_all`
returns all references. The helper uses registry metadata alone. Text output
includes upstream instructions and reports when citations or recommendations
are absent. Record output preserves the distinction between an omitted flag
and `false`. Dataset info and fetch metadata include the full references and
upstream instructions.

## Preprocessing

The optional top-level `preprocessing` object describes processing already
reflected in the registered artifacts. It has two required stage records:

- `upstream`: processing performed by the original producers or distributing
  collections before Datamonger acquired the data.
- `datamonger`: processing performed during Datamonger's preparation of the
  registered artifacts.

Each stage requires `status`:

- `unknown`: processing has not been established. Omit `steps`.
- `none`: evidence establishes that this stage applies no preprocessing. Omit
  `steps` and supply nonempty `evidence`.
- `documented`: at least one known step is recorded. Supply nonempty `steps` and
  `evidence` arrays. This records known processing, without claiming that the
  history is exhaustive.

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
methods, affected axes or columns, thresholds, class mappings, and the
population used to fit a transformation when known. Quote numeric and boolean
parameters as strings to preserve their documented precision without changing
registry number serialization. Omit unknown parameters rather than guessing
them.

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

Dataset metadata preserves both stages, including unknown history, and all
recorded steps and evidence. Clients treat the steps as descriptive metadata.

Some evidence strings refer to earlier individual decoder pages. The
[decoder reference](../spec/decoders.md) now covers those formats in one place.
Published indexes preserve the evidence strings from their release snapshots.
