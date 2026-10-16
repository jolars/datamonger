# Registries and reproducibility

A dataset version and a registry release identify different things. The dataset
reference `uci:iris@1` fixes a version of Iris. A registry release fixes the
collection of records that tells the client how to locate, decode, and verify
that dataset. Record both when you publish an analysis.

## Strong selectors

A `Registry` contains a release identifier, the SHA-256 digest of its index,
an index URL, and a schema version. The digest fixes the exact index bytes.
The URL supplies a retrieval location; matching a release name alone does not
establish that its bytes are the intended ones.

The bundled selector works without catalog discovery:

```julia
using Datamonger

registry = BUNDLED_REGISTRY
(
    release=registry.release,
    index_sha256=registry.index_sha256,
    index_url=registry.index_url,
)
```

For an explicit selector, retain all of those fields and reconstruct it with
`Registry(release, index_sha256, index_url)`. You can pass that object directly
to `fetch_data`, `fetch_artifact`, `data_info`, and `list_data`.

## Dataset references

These two calls select the same dataset version:

```julia
result = fetch_data("uci:iris@1"; registry, return_info=true)
result = fetch_data("iris"; source="uci", version="1", registry, return_info=true)
```

A bare name requires `source`. A qualified reference supplies its own source,
and a reference with `@version` supplies its own version. Do not repeat those
fields as keywords, even when the values agree. Omitting the version, as in
`uci:iris`, selects the registry's declared default. That is convenient for
exploration, but an explicit version communicates the analysis input directly.

With `return_info=true`, retain the returned `FetchInfo` alongside your results.
It records the canonical dataset ID, registry release and index digest,
artifact digests, verification status, canonical form, and canonical digest.
Record the Julia package version and your analysis environment separately.

## Selection precedence

An explicit per-call selector takes precedence over every implicit setting.
Otherwise, selection follows this order:

1. The session selector set by `set_registry!`.
2. The nearest `.datamonger/selector.json` in the current directory or its ancestors.
3. The bundled registry selector.

For a session-wide selection:

```julia
set_registry!(registry)
selected = active_registry()
set_registry!(nothing)
```

Clearing the session selector restores project discovery and then the bundled
fallback. It does not necessarily select the bundled registry if a project
selector is present.

A project selector is a JSON object with exactly these fields:

```json
{
  "schema_version": 1,
  "release": "1.1.0",
  "index_sha256": "1a7a4e0f7fea68ec22967661bf2e766d19a5ead670f1ed34d9454d50d22e377e",
  "index_url": "https://github.com/jolars/datamonger/releases/download/registry-v1.1.0/index.json"
}
```

Commit `.datamonger/selector.json` with an analysis to make the choice visible
to collaborators. A project selector pins the registry, not dataset versions or
the Julia dependency environment.

## Discover a release through the catalog

`resolve_registry` looks up a bare release name through an HTTPS catalog:

```julia
registry = resolve_registry("1.1.0")
```

This call requires network access. The catalog is mutable, so discovery is
trusted as strongly as the TLS session and catalog publisher. Record and reuse
the returned strong selector rather than repeating discovery on every run.
The client does not update a recorded selector automatically.

## Offline runs and preservation

The bundled registry index can be used offline immediately. Artifacts are
separate: first retrieve them online, then reuse the same selector and cache
with `offline=true`. A previously fetched custom registry index must also be
cached. Offline calls verify cached bytes rather than assuming they are valid.

A reproducible selector does not guarantee future access to an upstream-only
artifact. If your project requires preservation, retain an authorized copy
outside the disposable cache and follow the dataset's license and terms.
