# Datamonger normative specification

The revision 1 feature set is frozen. [`revision-1.md`](revision-1.md) defines
the profile and its versioned contract inventory:

- `identity.md` defines dataset identity, resolution, and release evolution.
- `retrieval.md` defines selectors, HTTP byte boundaries, fallback, and cache
  guarantees.
- `errors.md` defines the shared semantic failure categories and precedence.
- `index.md` defines generated client indexes and deterministic serialization.
- `canonical-form.md` defines byte-exact logical verification streams.
- `decoders/` defines the accepted CSV, TSV, LIBSVM, and SVMLight recipes.
- `schema/` contains closed Draft 2020-12 JSON Schemas for authoring and
  generated records.

Specification release candidate [`spec-v1-rc1`](revision-1.md#release-candidate)
freezes this inventory and pairs it with the strongly selected `candidate-0002`
registry. Any change that alters logical output or reinterprets existing bytes
requires a new specification candidate and a new decoder, canonical-form,
schema, or behavioral-contract version as appropriate.
