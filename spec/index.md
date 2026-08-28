# Provisional Index Format

This document specifies only the index subset used by vertical-proof slice 0A.
It is not a stable Datamonger specification.

## Strong selection

A registry is selected by a release identifier, the SHA-256 digest of the exact
index bytes, and a retrieval URL. The release identifier and digest form the
strong selector; the URL is only a retrieval location.

A client must hash the exact downloaded bytes before parsing JSON. It must then
reject an index whose embedded `release` differs from the selected release.

## Document shape

The UTF-8 JSON document contains:

- `schema_version`, which must equal `1`;
- `release`, a nonempty string;
- `defaults`, an array of `{source, name, version}` objects; and
- `datasets`, an array of dataset records using the manifest vocabulary in
  `DESIGN.md`.

Slice 0A supports one artifact, `distribution: upstream-only`, one
`delimited-text` representation, and one SHA-256 canonical verification record.
Unknown schema or decoder versions are errors rather than extension points.

The index fixture is not required to use canonical JSON. Deterministic index
generation is part of Milestone 1.
