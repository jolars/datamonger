# Provisional Index Format

This document specifies only the index subset used by the vertical proof.
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

The vertical proof supports one uncompressed, upstream-only artifact per
dataset; `delimited-text` and `libsvm` version 1 representations; vector and
sparse-matrix component expectations; and one SHA-256 canonical verification
record. Unknown schema or decoder versions are errors rather than extension
points.

The published proof index uses sorted, compact JSON with a final LF so its
generation can be checked mechanically. The complete deterministic `dm-index`
contract remains part of Milestone 1.
