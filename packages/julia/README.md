# Datamonger Julia client

This package implements Datamonger specification release candidate
`spec-v1-rc1`. It retrieves artifacts through strongly selected immutable
registry indexes, verifies their bytes, decodes the revision 1 CSV, TSV,
LIBSVM, and SVMLight representations, and verifies their canonical logical
digests.

The package is pre-release software and is not yet in Julia's General registry.
From a repository checkout:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()

using Datamonger
```

## Cache consent

Passing `cache_dir` gives Datamonger permission to use that path for the call.
Without it, Datamonger asks once before using the platform application cache in
an interactive session. If consent is absent or declined, it uses a
process-temporary directory under `tempdir()`.

For noninteractive work, configure the choice explicitly:

```console
export DATAMONGER_CACHE_CONSENT=true  # Persistent platform cache.
export DATAMONGER_CACHE_CONSENT=false # Session-temporary cache.
```

The package writes no persistent files at installation or startup. Cache growth
is limited to explicitly requested registry and artifact retrievals, eviction is
manual through `cache_clean()`, and `cache_info()` reports every
content-addressed entry. Datamonger performs no telemetry.

## Use

The bundled `proof-0001` index is the default trust root. Its artifacts are
retrieved on first use:

```julia
iris = fetch_data("iris"; source="uci")
heart = fetch_data("heart_scale"; source="libsvm")
```

For reproducible analysis, select an explicit version and retain the returned
metadata:

```julia
result = fetch_data(
    "iris";
    source="uci",
    version="1",
    return_info=true,
)
result.info.dataset_id
result.info.registry_release
result.info.registry_index_sha256
result.info.canonical_digest
```

Delimited representations return a `DataFrame` whose columns use
`Union{Missing,T}` where missing values occur. `int64` values remain exact Julia
`Int64`s. LIBSVM returns a `SparseDataset` with a Julia `SparseMatrixCSC` and an
exact `Int64` or `Float64` response. Representations too wide for a practical
CSC column-pointer array use the exported, read-only `CSRMatrix` instead.
`libsvm-split` returns a `SparseDatasetSplit` with separate `train` and `test`
datasets.

`data_info()` and `list_data()` inspect provenance, license, distribution, task,
and verification metadata without retrieving artifacts. `fetch_artifact()`
retrieves only verified artifact bytes. `offline=true` forbids network access
and requires the selected index and artifacts to be bundled or already cached.
Decoded verification is enabled by default; `verify_decoded=false` disables
only shape and canonical verification, never artifact verification.

## Registry selection

An explicit strong selector fixes a release and exact index bytes:

```julia
selected = Datamonger.Registry(
    "2026.08",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "https://registry.example/2026.08/index.json",
)
result = fetch_data("iris"; source="uci", registry=selected)
```

Selection precedence is a per-call `registry` keyword, `set_registry!()` for the
session, the nearest `.datamonger/selector.json`, and the bundled selector.
`resolve_registry()` discovers a selector by bare release through a mutable
HTTPS catalog. That lookup is trusted only as strongly as the TLS session; the
returned release and digest become reproducible when recorded and reused.

## Error taxonomy and cache management

Expected failures derive from `DatamongerError`. The public concrete types map
directly to revision 1 categories: `UnknownDatasetError`,
`UnsupportedRegistryError`, `UnsupportedDecoderError`,
`ArtifactUnavailableError`, `OfflineError`, `RetrievalLocationsError`,
`ArtifactIntegrityError`, `DecodedIntegrityError`, `CacheError`, and
`DecodeError`. More specific registry and artifact-selection failures are also
exported.

`cache_info()` verifies and inventories cached indexes and artifacts.
`cache_clean(dataset="uci:iris@1")` selects artifacts referenced by one
canonical dataset version; `older_than=Day(30)` selects old entries, and the
filters intersect. Calling `cache_clean()` without filters selects the entire
cache. Active readers and publishers are skipped, and eviction is never
automatic.

The project code is MIT-licensed. Datasets retain their own licenses and terms;
registry inclusion is not a license grant or a preservation guarantee.
