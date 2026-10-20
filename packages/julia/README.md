# Datamonger Julia client

This package implements Datamonger specification revision 1. It retrieves
artifacts through strongly selected immutable registry indexes, verifies their bytes, decodes the revision 1 CSV, TSV,
LIBSVM, and SVMLight representations, and verifies their canonical logical
digests.

The package is pre-release software and is not yet in Julia's General registry.
From a repository checkout:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()
include("tools/dm_julia_core.jl")

using Datamonger
```

Decoding, artifact decompression, and canonical hashing use the Rust
`datamonger-core` library through C ABI 1. Registry resolution, retrieval,
caching, metadata, and public return types remain in Julia. Source checkouts
require Rust 1.82 or newer for the build command above; rebuild after native
edits. The local binding is ignored by Git. Release preparation pins prebuilt
artifacts for Linux x86-64 and ARM64 (glibc 2.17+), macOS Intel and Apple Silicon,
and Windows x86-64, so installed releases need no Rust compiler. The library is
loaded on first decode or canonical operation. Julia installs release artifacts
during package instantiation; decoding never downloads executable code, including
in offline calls.

## Tutorials

The [offline data workflow](tutorials/offline-workflow.md) walks through verified
retrieval, missing values, sparse data, train/test splits, and cache management.
The [reproducibility guide](tutorials/reproducibility.md) explains registry
selectors and dataset versions. Diplodocus publishes both articles with the
[Julia documentation](https://datamonger.dev/packages/julia/).

## Cache

Datamonger uses the platform application cache by default. Passing `cache_dir`
uses that path for the call instead. For temporary caching, create a process
directory and pass it consistently:

```julia
temporary_cache = mktempdir()
iris = fetch_data("iris"; source="uci", cache_dir=temporary_cache)
```

Julia manages native libraries in its artifact depot. Datamonger creates its
dataset cache only when requested. Dataset cache growth
is limited to explicitly requested registry and artifact retrievals, eviction is
manual through `cache_clean()`, and `cache_info()` reports every
content-addressed entry. Datamonger performs no telemetry.

## Use

The bundled stable index is the default trust root. Its artifacts are
retrieved on first use:

```julia
iris = fetch_data("iris"; source="uci")
heart = fetch_data("heart_scale"; source="libsvm")
```

`fetch_data()`, `data_info()`, and `fetch_artifact()` also accept the dataset
references used by the CLI:

```julia
iris = fetch_data("uci:iris")
iris_v1 = fetch_data("uci:iris@1")
iris_v1 = fetch_data("uci:iris"; version="1")
```

A bare name requires `source`. Omit `source` for qualified references, and omit
`version` when the reference embeds it. Duplicate arguments raise an error even
when the values agree. An omitted version selects the registry's declared
default.

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

The `named-splits` assembly returns a `DatasetSplits` mapping in recipe order.
Access provider splits as `data["train"]`, `data["validation"]`, or `data["test"]`.
Each value is a table or sparse dataset, and feature-only tables omit responses.
The [named splits contract](../../spec/decoders/named-splits-v1.md) requires
manifest schema 4 and preserves each split's original name and row membership.

`data_info()` and `list_data()` inspect provenance, license, distribution, task,
and verification metadata without retrieving artifacts. `fetch_artifact()`
retrieves only verified artifact bytes. `offline=true` forbids network access
and requires the selected index and artifacts to be bundled or already cached.
Decoded verification is enabled by default; `verify_decoded=false` disables
only shape and canonical verification, never artifact verification.

`data_info(...).preprocessing` and fetch results requested with `return_info=true`
expose upstream and Datamonger processing in version 3 registries. Each stage
distinguishes `unknown`, `none`, and `documented` and preserves known steps,
string parameters, and evidence references. Missing metadata is `nothing`,
including in older bundled snapshots. Fetching does not apply the described
transformations. See the [preprocessing contract](../../spec/preprocessing.md).

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

## Dataset citations

`cite_data("uci:wine-quality@1")` returns curated citation text without
retrieving dataset artifacts. Use `format="records"` for reference records and
`include_all=true` to include every reference. A reference may have a
`dataset`, `paper`, or `collection` role, a note, and an upstream recommendation
flag. Multiple references can be recommended together. Roles do not imply
recommendations.

By default, references marked as recommended are selected. If no recommendation
flags are recorded, all references are returned and text output explains that
the recommendation is unknown. Missing citations produce an empty vector of
records or an explicit text message. Legacy single citations remain supported.

`data_info(...).citations` and `fetch_data(...; return_info=true).info.citations`
contain every reference from the selected registry record.
`citation_instructions` preserves upstream instructions, including requests to
cite several references together. No bibliographic lookups are performed.
