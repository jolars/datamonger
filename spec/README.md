# Datamonger normative specification

Specification revision 1 is frozen and stable. [`revision-1.md`](revision-1.md)
defines the profile and its versioned contract inventory:

- `identity.md` defines dataset identity, resolution, and release evolution.
- `retrieval.md` defines selectors, HTTP byte boundaries, fallback, and cache
  guarantees.
- `errors.md` defines the shared semantic failure categories and precedence.
- `index.md` defines generated client indexes and deterministic serialization.
- `canonical-form.md` defines byte-exact logical verification streams.
- `decoders/` defines the accepted CSV, TSV, LIBSVM, and SVMLight recipes.
- `schema/` contains closed Draft 2020-12 JSON Schemas for authoring and
  generated records.

Specification release [`spec-v1`](revision-1.md#stable-release) freezes this
inventory and pairs it with the strongly selected `2026.09` registry. Python,
R, and Julia pass the shared conformance corpus and reproduce every registry
verification record. Any change that alters logical output or reinterprets
existing bytes requires a later specification revision and a new decoder,
canonical-form, schema, or behavioral-contract version as appropriate.
