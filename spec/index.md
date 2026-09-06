# Registry Index Format Version 1

This document is normative. Manifests and release sources are authored in YAML;
clients consume only generated JSON indexes and must never parse registry YAML.

## Document shape

An index is a UTF-8 JSON object validated by `schema/index-v1.schema.json`. It
contains:

- `schema_version`, equal to `1`;
- `release`, matching `[a-z0-9][a-z0-9._-]*`;
- `defaults`, an array of unique `{source, name, version}` records;
- `datasets`, an array of unique manifest records; and
- when nonempty, `errata`, an array of approved erratum records.

Every default must identify a dataset in the same index, and each `(source,
name)` has at most one default. Dataset records use the manifest schema version
declared in the record. Unknown index, manifest, canonical-form, or decoder
versions are errors rather than extension points. A missing version is not
version 1.

## Deterministic generation

`dm-index` validates release sources and referenced YAML values before
generation. Duplicate YAML mapping keys, non-JSON scalar types, absolute paths,
and paths escaping the repository root are errors.

Each release source carries a nonnegative `sequence` unique within its registry
tree. It is authoring metadata and is not emitted. Only lower-sequence releases
are historical baselines, so checking an old release remains valid after newer
releases exist.

The generated index is serialized as follows:

1. sort `datasets` by `(source, name, version)` and `defaults` by the same key;
2. preserve all other array order because it may carry component, retrieval, or
   append-only semantics;
3. sort every JSON object key by Unicode code point;
4. emit strings and integers using JSON syntax: escape quotation mark and
   reverse solidus, use `\b`, `\t`, `\n`, `\f`, and `\r` for those controls,
   use lowercase `\u00xx` for other controls, never escape solidus, and emit
   non-ASCII Unicode as UTF-8 rather than ASCII escapes;
5. emit no insignificant whitespace; and
6. append exactly one LF byte.

Schema version 1 contains no non-integer JSON numbers. Equivalent parsed source
trees therefore produce byte-identical indexes independent of YAML key order,
checkout path, working directory, locale, timezone, or process hash seed.

Every integer carried in a version 1 registry JSON or YAML document must be
between zero and `9007199254740991` (`2^53 - 1`), inclusive, unless its schema
gives a smaller bound. This restriction preserves exact values in all
target-language JSON implementations. Wider `uint64` fields in the canonical
binary form are framing widths, not permission to publish larger registry
integers.

The distributed selector contains `schema_version`, equal to `1`, plus
`release`, `index_sha256`, and `index_url`. The URL is an absolute HTTP or HTTPS
URL. The digest is SHA-256 over the complete generated index including its
final LF. `schema_version` is not part of the strong `(release, index_sha256)`
identity. The selector is serialized by the same JSON rules.

Generated indexes and selectors are never edited manually. Creating an absent
output is permitted; replacing an existing output with different bytes is an
immutable-release failure. Check mode performs all validation and byte
comparisons without writing.

## Release catalog

The HTTPS release catalog is a mutable convenience index validated by
`schema/catalog-v1.schema.json`. It contains `schema_version`, equal to `1`, and
`releases`, an array of strong selector records. Release identifiers are unique,
and records are sorted by `release` under the deterministic serialization rules
above. A catalog contains no floating aliases such as `latest`.

The catalog is regenerated from validated immutable release outputs. Unlike an
index or selector, it changes when a release is added. Resolving a bare release
through it is therefore TLS-trusted discovery; the resulting selector becomes
reproducible only when its release, digest, and index URL are recorded and
reused without another catalog lookup.

## Release comparison

Before generating a candidate, `dm-index` compares every repeated dataset
identifier with all earlier indexes in the registry tree under the rules in
`identity.md`. It also validates artifact and input references, policy/location
agreement, expected component shape, and approved errata. These semantic checks
are required in addition to JSON Schema validation.

The release authoring source is itself a version 1 document and must contain
`schema_version`, equal to `1`. Its `sequence` is a nonnegative exact JSON
integer, its release uses the grammar above, and its GitHub tag uses
`[A-Za-z0-9][A-Za-z0-9._-]*`.
