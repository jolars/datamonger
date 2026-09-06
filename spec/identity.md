# Dataset Identity Version 1

This document is normative. The key words **must**, **must not**, **should**, and
**may** describe requirements on registry tooling and clients.

## Identifier

A dataset identifier is the ordered triple `(source, name, version)`.

- `source` and `name` must match `[a-z0-9][a-z0-9._-]*`.
- `version` must match `[A-Za-z0-9][A-Za-z0-9._+-]*`.
- All three components are case-sensitive ASCII strings. A version is opaque;
  clients must not infer an ordering from its spelling.
- The canonical serialization is `source:name@version`, with no escaping or
  additional whitespace.

`source` identifies a provenance collection. It is not an artifact location.
The serialized identifier is used in logs, lockfiles, relations, and returned
metadata; user-facing APIs may accept the three components separately.

## Resolution

Resolution always occurs within one strongly selected registry index. An
explicit version selects the exactly matching triple. If the version is
omitted, the index must contain exactly one matching entry in `defaults`; that
entry supplies the version. A missing or ambiguous match is an unknown-dataset
failure.

An omitted version is a convenience query, not a reproducible identifier. A
client must report the resolved canonical identifier, registry release, and
index digest with the result.

## Dataset-version identity

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

## Release evolution

For a dataset identifier present in an earlier and a later release:

- identity-bearing fields must be equal;
- every earlier task must remain present with the same name and value; task
  array order is not semantic, and new uniquely named tasks may be added;
- every earlier component expectation must remain unchanged; and
- every earlier verification record must remain present unchanged; new records
  may be appended.

A dataset may be absent from a later release without changing the earlier
release. Default selections may change between releases.

An incorrect component expectation or verification record may be corrected
only by a later release containing an approved erratum. A verification erratum
retains and revokes the original record and appends its replacement. A
component erratum identifies the exact original record and permits the later
record to contain its exact replacement. Earlier releases remain unchanged.

Published decoder versions are immutable. A logical-output change requires a
new decoder version and therefore a new dataset version. A canonical-form
version is verification framing rather than dataset identity; a later release
may append a digest for a newer canonical-form version without changing the
dataset version.

For each `(canonical_form, algorithm)` pair, a dataset must have exactly one
non-revoked verification record. Multiple records with that pair are valid only
when included errata revoke every superseded record. When more than one
supported pair is available, a client uses the last supported, non-revoked
record in manifest order and reports that choice.

## Tasks

A task uses either top-level roles or named `splits`, never both. Classification
and regression tasks require a `target` at the top level or in every split;
`features` is optional. Unsupervised tasks require `features` at the top level
or in every split and must not declare a `target`. Feature-array order is
semantic. Split names are unique. Within one top-level or split role record,
component references must be unique, must resolve to the decoded
representation, and must not name the same component as both a feature and the
target.
