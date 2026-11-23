# Datamonger format reference

- [Registry and retrieval](registry.md) covers dataset identity, index
  generation, artifact verification, caching, and errors.
- [Decoders](decoders.md) defines how artifact bytes become logical datasets.
- [Canonical form](canonical-form.md) defines the bytes used for decoded
  verification.
- [JSON Schemas](schema/) define versioned authoring and generated records.
- [Conformance fixtures](../tests/conformance/) exercise the shared behavior.

See the [registry guide](../registry/README.md) for authoring and releasing
datasets. The [spec-v1 tag](https://github.com/jolars/datamonger/tree/spec-v1/spec)
preserves the original specification and its release history.
