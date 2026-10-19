# Datamonger TODO

- [x] Migrate Python decoding, decompression, and canonical verification to
  `datamonger-core`, introduced in
  [510c863](https://github.com/jolars/datamonger/commit/510c8631bd8c063454d933d3998fe8f878a02dc1).
  Add native bindings and wheel builds while preserving public return types,
  errors, and client-side registry resolution, retrieval, caching, and metadata.
  Validate against the independent Python implementation and shared conformance
  corpus before replacing the current backend.
- [x] Migrate Julia decoding, decompression, and canonical verification to
  `datamonger-core`. Define the C ABI and Julia bindings, package native artifacts
  for supported platforms, and preserve public return types, errors, and
  client-side registry resolution, retrieval, caching, and metadata. Validate
  against the independent Julia implementation and shared conformance corpus
  before replacing the current backend.
