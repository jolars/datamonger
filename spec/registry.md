# Registry and retrieval

## Dataset identity

### Identifier

A dataset identifier is the ordered triple `(source, name, version)`.

- `source` and `name` must match `[a-z0-9][a-z0-9._-]*`.
- `version` must match `[A-Za-z0-9][A-Za-z0-9._+-]*`.
- All three components are case-sensitive ASCII strings. A version is opaque;
  clients must not infer an ordering from its spelling.
- The canonical serialization is `source:name@version`, with no escaping or
  additional whitespace.

`source` identifies a provenance collection. It is not an artifact location. The
serialized identifier is used in logs, lockfiles, relations, and returned
metadata; user-facing APIs may accept the three components separately.

### Resolution

Resolution always occurs within one strongly selected registry index. An
explicit version selects the exactly matching triple. If the version is omitted,
the index must contain exactly one matching entry in `defaults`; that entry
supplies the version. A missing or ambiguous match is an unknown-dataset
failure.

An omitted version is a convenience query, not a reproducible identifier. A
client must report the resolved canonical identifier, registry release, and
index digest with the result.

### Dataset-version identity

The following fields are identity-bearing:

- `source`, `name`, and `version`;
- each artifact's `name`, `size`, `sha256`, `format`, and `compression`; and
- the complete representation recipe: `decoder`, `decoder_version`, `inputs`,
  and `options`.

Changing any identity-bearing field requires a new dataset version. Artifact
array order is not identity-bearing; artifact names are unique, and inputs
address artifacts by name. Representation input and option object keys are
compared as mappings, while any arrays inside the recipe retain their declared
order.

Retrieval locations, descriptions, provenance, licensing clarifications,
relations, distribution and preservation metadata, tasks, expected shapes, and
verification attestations are release-scoped. They may evolve only under the
rules below.

### Release evolution

For a dataset identifier present in an earlier and a later release:

- identity-bearing fields must be equal;
- every earlier task must remain present with the same name and value; task
  array order is not semantic, and new uniquely named tasks may be added;
- every earlier component expectation must remain unchanged; and
- every earlier verification record must remain present unchanged; new records
  may be appended.

A dataset may be absent from a later release without changing the earlier
release. Default selections may change between releases.

An incorrect component expectation or verification record may be corrected only
by a later release containing an approved erratum. A verification erratum
retains and revokes the original record and appends its replacement. A component
erratum identifies the exact original record and permits the later record to
contain its exact replacement. Earlier releases remain unchanged.

Published decoder versions are immutable. A logical-output change requires a new
decoder version and therefore a new dataset version. A canonical-form version is
verification framing rather than dataset identity; a later release may append a
digest for a newer canonical-form version without changing the dataset version.

For each `(canonical_form, algorithm)` pair, a dataset must have exactly one
non-revoked verification record. Multiple records with that pair are valid only
when included errata revoke every superseded record. When more than one
supported pair is available, a client uses the last supported, non-revoked
record in manifest order and reports that choice.

### Tasks

A task uses either top-level roles or named `splits`, never both. For manifest versions 1 through 3, classification
and regression tasks require a `target` at the top level or in every split;
`features` is optional. Unsupervised tasks require `features` at the top level
or in every split and must not declare a `target`. Feature-array order is
semantic. Split names are unique. Within one top-level or split role record,
component references must be unique, must resolve to the decoded representation,
and must not name the same component as both a feature and the target.

Manifest version 4 adds [feature-only split roles](decoders.md#split-tasks).

## Registry indexes

### Document shape

Clients read UTF-8 JSON indexes generated from YAML manifests and release
sources. The [JSON Schemas](schema/) define the shape of each index and the
manifest versions it accepts. The generator chooses the highest manifest
schema version selected for the release.

Every default must identify a dataset in the same index, and each
`(source, name)` has at most one default. Dataset records use the manifest
schema version declared in the record. Unknown index, manifest, canonical-form,
or decoder versions are errors rather than extension points. A missing version
is not version 1.

### Deterministic generation

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
   reverse solidus, use `\b`, `\t`, `\n`, `\f`, and `\r` for those controls, use
   lowercase `\u00xx` for other controls, never escape solidus, and emit
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
URL. The digest is SHA-256 over the complete generated index including its final
LF. `schema_version` is not part of the strong `(release, index_sha256)`
identity. The selector is serialized by the same JSON rules.

Generated indexes and selectors are never edited manually. Creating an absent
output is permitted; replacing an existing output with different bytes is an
immutable-release failure. Check mode performs all validation and byte
comparisons without writing.

### Release catalog

The HTTPS release catalog is a mutable convenience index validated by
`schema/catalog-v1.schema.json`. It contains `schema_version`, equal to `1`, and
`releases`, an array of strong selector records. Release identifiers are unique,
and records are sorted by `release` using the same serialization rules. A catalog contains no floating aliases such as `latest`.

The catalog is regenerated from validated immutable release outputs. It changes when a release is added.

### Release comparison

Before generating a candidate, `dm-index` compares every repeated dataset
identifier with all earlier indexes using the [release evolution rules](#release-evolution).
It also validates artifact and input references, agreement between distribution
policies and locations, expected component shape, and approved errata. These semantic checks
are required in addition to JSON Schema validation.

The release authoring source is itself a version 1 document and must contain
`schema_version`, equal to `1`. Its `sequence` is a nonnegative exact JSON
integer, its release uses the grammar above, and its GitHub tag uses
`[A-Za-z0-9][A-Za-z0-9._-]*`.

## Retrieval

### Registry selection

A strong registry selector is `(release, index_sha256)`. Its versioned document
also carries `schema_version`; `index_url` is its retrieval location. Index and
artifact locations are absolute HTTP or HTTPS URLs with lower-case schemes. A
client must validate the release and lowercase SHA-256 grammars, hash the exact
retrieved index bytes before parsing them, parse the bytes as UTF-8 JSON, and
then require the embedded `release` and `schema_version` to match its supported
contract.

Resolving a bare release through the HTTPS catalog discovers a selector. Clients
expose the resolved selector so callers can pin the digest and reuse the
selector without another lookup. The digest verifies the index against the
chosen selector, whose authenticity depends on how it was obtained.

### Artifact byte boundary

An artifact is the response content after HTTP transfer framing and declared
HTTP content codings have been removed, but before manifest-declared artifact
compression is removed. Its `size` and `sha256` apply to those bytes.

For every HTTP request, a client must:

1. send `Accept-Encoding: identity`;
2. accept no content coding, `identity`, `gzip`, or the legacy alias `x-gzip`;
3. remove declared content codings in reverse application order;
4. reject malformed, truncated, concatenated, multiply declared, or unsupported
   coded streams; and
5. size-check and hash the decoded content incrementally.

Version 1 supports at most one non-identity content coding. Transfer coding and
`Content-Length` are transport metadata and are not included in artifact bytes.
Redirects may be followed under ordinary HTTP semantics; the final bytes must
still satisfy the registered size and digest.

Artifact compression is taken only from the manifest. It must not be inferred
from a URL, media type, or filename. Retrieval verifies and caches the
compressed artifact before a decoder removes `gzip` or `bzip2` compression.

### Location fallback

Locations are attempted in manifest order. A transport failure, unsupported or
malformed content coding, size mismatch, or digest mismatch discards the
temporary bytes and permits the next location to be tried. Invalid bytes must
never become a cache entry.

Location URLs must be unique within an artifact. A redirect target must also be
an absolute HTTP or HTTPS URL; redirects do not create or alter artifact
identity.

If all locations fail, diagnostics must retain each attempted location and
classify the result as an integrity failure when any location returned complete
but incorrectly sized or hashed bytes; otherwise it is an availability failure.
`metadata-only` artifacts fail before network access. Artifact verification can
never be disabled.

### Cache semantics

Registry indexes and artifacts are cached by SHA-256 in client-private cache
roots. A cache path is not proof of integrity: clients must recheck the complete
size and digest before use.

A download is written to a temporary file in the destination filesystem,
flushed, verified, and atomically published. Concurrent publishers may perform
duplicate work, but readers must observe either the previous complete object or
the new complete object—never a partial file. A corrupt existing object is
quarantined or removed before replacement.

Each client must implement per-object publisher, reader, and cleaner leases.
Publication excludes cleaners; an active reader excludes cleaners; cleaners skip
active objects. Lease recovery must distinguish a live owner from a stale record
after process or host failure. Client-specific paths and primitives may differ,
but these observable guarantees may not.

Offline retrieval uses verified cached indexes and artifacts only. It must not
silently select a different release or dataset version. Cache eviction is
manual, never automatic, and must report which objects were skipped because they
were active.

Decoded verification is enabled by default after retrieval and decoding. A
caller may explicitly disable only decoded verification; returned metadata must
then label the result as artifact-verified rather than decoded-verified.

## Errors

Clients expose the following categories through their native error types.

### Categories

  | Category               | Meaning                                                                                                                  |
  | ---------------------- | ------------------------------------------------------------------------------------------------------------------------ |
  | `unknown-dataset`      | The selected registry has no matching dataset or version.                                                                |
  | `unsupported-registry` | A registry, dataset record, or schema version requires unsupported semantics.                                            |
  | `unsupported-decoder`  | A representation requires an unsupported decoder, decoder version, artifact format, compression, or verification record. |
  | `artifact-unavailable` | Distribution policy marks a required artifact as `metadata-only`.                                                        |
  | `artifact-offline`     | Offline mode was requested, but no valid cached artifact exists.                                                         |
  | `retrieval-exhausted`  | Every retrieval location failed, and none returned complete bytes with a size or digest mismatch.                        |
  | `artifact-integrity`   | After fallback was exhausted, at least one location returned complete bytes that failed the registered size or digest.   |
  | `decoded-integrity`    | Decoded logical values, shape, or canonical digest do not match `expect`.                                                |
  | `cache`                | The client cannot inspect, lease, publish, read, or remove cache state safely.                                           |
  | `decode`               | Verified artifact bytes do not satisfy their supported representation recipe.                                            |

### Classification rules

Classification records the furthest meaningful stage reached by the operation.
An unknown dataset fails during resolution. A metadata-only artifact fails
before network access, and offline retrieval never attempts a location.
Unsupported registry and decoder behavior fails explicitly rather than being
reinterpreted under a supported version.

Location failures are recoverable while an untried location remains. If a later
location succeeds, no retrieval error is reported. Once all locations fail, the
result is `artifact-integrity` when any location returned complete but
incorrectly sized or hashed artifact bytes; otherwise it is
`retrieval-exhausted`. Diagnostics must retain every attempted location.
Malformed or unsupported HTTP coding and truncated responses are location
failures, not artifact-integrity failures, because they do not produce complete
artifact bytes.

Artifact integrity is checked before decoding. Consequently, malformed data with
a valid artifact size and digest is `decode`, while validly decoded logical
values that disagree with `expect` are `decoded-integrity`. A cache failure is
reported as `cache` rather than being treated as an unavailable location.

Clients may expose additional subclasses for registry selection, registry
retrieval, artifact selection, or other client-specific diagnostics. Such
refinements must remain catchable as their documented public base category and
must not merge any of the categories above.
