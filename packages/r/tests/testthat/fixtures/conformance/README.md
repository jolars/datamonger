# Datamonger conformance corpus

This directory is the language-neutral conformance descriptor schema version 1.
Paths in `cases.json` are relative to this directory. Every listed case is
required for a specification revision 1 implementation claim.

Each decoder case names its `decoder` and `decoder_version`, supplies the
complete recipe, and gives the expected digest under the document's
`canonical_form`. A single-artifact case names one input path; an assembly case
maps each specified input role to its path. `canonical/cases.json` names its
`canonical_form` and supplies logical values and exact canonical bytes as
lowercase hexadecimal, avoiding a language-specific fixture serializer.
`fuzz-regressions.json` stores minimized byte inputs with an explicit decoder
version and required failure stage. `malformed.json` also names its decoder and
error-taxonomy versions, while `errors.json` names the shared
`error_taxonomy_version` and enumerates its categories.

Each decoder case names its immutable test-registry dataset so clients can
exercise the same golden through their public registry API. Implementations may
use different native containers, exception types, and messages, but must agree
on logical values, canonical bytes, success or failure, and semantic failure
categories.

`preprocessing.json` exercises the manifest version 3 metadata extension,
including older manifests with no history, explicit unknown and absent
processing, ordered steps and parameters, and malformed records. Each case
declares its manifest schema version and expected validity. Implementations
must preserve valid metadata without changing decoded values or verification.

`named-splits.json` exercises the `named-splits` version 1 extension and manifest
schema version 4. It includes complete manifests, artifact paths, expected
native values, independent canonical-form 1 golden bytes, and invalid recipes.
Clients must preserve declared split order, names, membership, and absent test
labels, including empty tables and names containing Unicode and path punctuation.
These cases extend the corpus without changing the revision 1 implementation
claim. Golden bytes were produced by the independent Python decoder and
canonical encoder in `packages/python/tests/reference`, with names qualified
according to `spec/decoders/named-splits-v1.md`.

`libsvm-v2.json` adds explicit positive, negative, and underflowed zeros to the
small LIBSVM fixture. All four decoders must reproduce the existing fixture's
canonical-form 1 digest after omitting these entries. Decoder v1 continues to
reject this input. The version 1 fixture and its digest remain unchanged.
