# Semantic Error Taxonomy Version 1

This document is normative. Clients may use idiomatic exception, condition, or
result types, but they must expose the semantic categories below. Human-readable
messages and transport-library errors are diagnostic details, not categories.

## Categories

| Category | Meaning |
| --- | --- |
| `unknown-dataset` | The selected registry has no matching dataset or version. |
| `unsupported-registry` | A registry, dataset record, or schema version requires unsupported semantics. |
| `unsupported-decoder` | A representation requires an unsupported decoder, decoder version, artifact format, compression, or verification record. |
| `artifact-unavailable` | Distribution policy marks a required artifact as `metadata-only`. |
| `artifact-offline` | Offline mode was requested, but no valid cached artifact exists. |
| `retrieval-exhausted` | Every retrieval location failed, and none returned complete bytes with a size or digest mismatch. |
| `artifact-integrity` | After fallback was exhausted, at least one location returned complete bytes that failed the registered size or digest. |
| `decoded-integrity` | Decoded logical values, shape, or canonical digest do not match `expect`. |
| `cache` | The client cannot inspect, lease, publish, read, or remove cache state safely. |
| `decode` | Verified artifact bytes do not satisfy their supported representation recipe. |

## Classification rules

Classification records the furthest meaningful stage reached by the operation.
An unknown dataset fails during resolution. A metadata-only artifact fails before
network access, and offline retrieval never attempts a location. Unsupported
registry and decoder behavior fails explicitly rather than being reinterpreted
under a supported version.

Location failures are recoverable while an untried location remains. If a later
location succeeds, no retrieval error is reported. Once all locations fail, the
result is `artifact-integrity` when any location returned complete but
incorrectly sized or hashed artifact bytes; otherwise it is
`retrieval-exhausted`. Diagnostics must retain every attempted location.
Malformed or unsupported HTTP coding and truncated responses are location
failures, not artifact-integrity failures, because they do not produce complete
artifact bytes.

Artifact integrity is checked before decoding. Consequently, malformed data
with a valid artifact size and digest is `decode`, while validly decoded logical
values that disagree with `expect` are `decoded-integrity`. A cache failure is
reported as `cache` rather than being treated as an unavailable location.

Clients may expose additional subclasses for registry selection, registry
retrieval, artifact selection, or other client-specific diagnostics. Such
refinements must remain catchable as their documented public base category and
must not merge any of the categories above.
