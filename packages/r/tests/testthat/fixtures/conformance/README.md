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
