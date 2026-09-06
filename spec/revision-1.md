# Datamonger Specification Revision 1

This document is normative. Revision 1 is a feature-frozen profile of the
independently versioned contracts below. Equal version numbers do not imply that
two contracts share a lifecycle.

| Contract | Revision 1 version | Authority |
| --- | --- | --- |
| Dataset identity and release evolution | 1 | `identity.md` |
| Registry and artifact retrieval | 1 | `retrieval.md` |
| Semantic error taxonomy | 1 | `errors.md` |
| Registry index format | 1 | `index.md` |
| Canonical logical form | 1 | `canonical-form.md` |
| Delimited-text decoder | 1 | `decoders/delimited-text-v1.md` |
| LIBSVM and split decoder | 1 | `decoders/libsvm-v1.md` |
| Manifest schema | 1 | `schema/manifest-v1.schema.json` |
| Generated-index schema | 1 | `schema/index-v1.schema.json` |
| Release-source schema | 1 | `schema/release-source-v1.schema.json` |
| Erratum schema | 1 | `schema/erratum-v1.schema.json` |
| Strong-selector schema | 1 | `schema/selector-v1.schema.json` |
| Release-catalog schema | 1 | `schema/catalog-v1.schema.json` |
| Language-neutral conformance descriptors | 1 | `../tests/conformance/README.md` |

## Feature set

Revision 1 includes immutable, digest-selected registry indexes; explicit
dataset identity and default resolution; HTTP and HTTPS artifact retrieval;
private content-addressed caches; offline reuse; CSV, TSV, LIBSVM, and SVMLight
artifacts; `none`, `gzip`, and `bzip2` artifact compression; tabular and sparse
native results; `float64`, `int64`, `string`, and `bool` logical values; named
classification, regression, and unsupervised tasks; canonical SHA-256
verification; and the core fetch, metadata, listing, and cache-management
operations.

Revision 1 does not include registry signing, controlled mirrors or a
preservation guarantee, project lockfiles beyond a strong registry selector,
private data, transformations, huge-data streaming, additional modalities or
logical types, or task-oriented data extraction. Those features require a later
specification revision and whichever new component-contract versions they use.

## Version dispatch and change control

Every revision 1 wire or authoring document carries its own `schema_version`. A
decoder recipe carries `decoder_version`, and a verification record carries
`canonical_form`. A client must select semantics from the version in the
document or record and reject an unsupported version before interpreting
version-dependent fields. A missing version is not version 1.

A schema version governs the complete JSON document bearing it. All revision 1
schemas are closed; adding a field, enum value, or alternative record shape
requires a new schema version. Changing decoder output requires a new decoder
version and dataset version. Changing canonical bytes requires a new
canonical-form version. Changing the meaning or precedence of a semantic error
category requires a new error-taxonomy version. Editorial clarifications that
do not change accepted inputs, output, identity, retrieval behavior, or failure
classification may retain the existing version.

The conformance documents carry `schema_version` for their descriptor shape and
also name the decoder, canonical-form, or error-taxonomy version they exercise.
An implementation claim for revision 1 covers every revision 1 conformance
case.
