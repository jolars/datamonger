# Datamonger for Julia <img src="https://raw.githubusercontent.com/jolars/datamonger/refs/heads/main/assets/logo.png" align="right" width="139" alt="A datamonger carrying a box of data" />

[![CI](https://github.com/jolars/datamonger/actions/workflows/ci.yml/badge.svg)](https://github.com/jolars/datamonger/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23692468-blue)](https://doi.org/10.5281/zenodo.23692468)

Datamonger retrieves public research datasets in Julia. It downloads and caches
dataset files, returns native data frames and sparse matrices, and verifies that
the decoded values match those in the registry. Python and R clients share the
same registry and verification contracts.

Each dataset has a versioned record describing its source, format, provenance,
license, and citations. You can pin the registry and dataset version to keep an
analysis reproducible.

## Installation

Requires Julia 1.10 or newer. From a repository checkout, run these commands at
the repository root:

```julia
using Pkg

Pkg.activate("packages/julia")
Pkg.instantiate()

include("tools/dm_julia_core.jl")

using Datamonger
```

Building the native decoder from source requires Rust 1.82 or newer. Rebuild it
after native code changes. See the [contributor
guide](https://github.com/jolars/datamonger/blob/main/CONTRIBUTING.md) for
development setup and native builds.

## Usage

Load a dataset by its `source:name` reference:

```julia
using Datamonger

iris = fetch_data("uci:iris")
heart = fetch_data("libsvm:heart_scale")
```

Delimited datasets return a `DataFrame`, with `missing` values where needed.
LIBSVM datasets return a `SparseDataset` with a sparse `features` matrix and a
`response` vector:

```julia
first(iris, 5)
size(heart.features), length(heart.response)
```

Sparse features usually use Julia's `SparseMatrixCSC`. Representations too wide
for a practical column-pointer array use the exported, read-only `CSRMatrix`
instead. Integer values remain exact `Int64`s.

Datasets with train/test splits return a `SparseDatasetSplit` with separate
`train` and `test` fields. Datasets with provider-named splits return a
`DatasetSplits` mapping, accessed with keys such as `data["train"]` and
`data["validation"]`. Datamonger preserves each split's name and row membership.

Files are downloaded on first use and kept in a verified local cache. The
registry index is bundled with the package, so you can browse metadata without
network access. Dataset files are downloaded separately.

Use `list_data()` to browse the registry, `data_info()` to inspect a dataset's
metadata, and `cite_data()` to retrieve its citations without downloading data:

```julia
datasets = list_data()
info = data_info("uci:iris")
println(info.license)
println(cite_data("uci:iris"))
```

To retrieve a verified file without decoding it, use `fetch_artifact()`:

```julia
iris_csv = fetch_artifact("uci:iris")
```

This returns a path in the cache. For datasets with several artifacts, select
one explicitly, for example with `artifact="train"`. Files retain their
registered format and compression.

## Reproducibility

Select an explicit dataset version and retain the verification metadata with
your analysis:

```julia
result = fetch_data("uci:iris@1"; return_info=true)
iris = result.data
println(result.info.dataset_id)
println(result.info.registry_release, " ", result.info.registry_index_sha256)
println(result.info.canonical_digest)
```

`return_info=true` wraps the decoded data with its resolved identity, registry
selector, artifact digests, and decoded-verification record. Datamonger checks
artifact sizes and SHA-256 hashes, then verifies decoded shapes and a canonical
SHA-256 digest.

Dataset operations also accept separate arguments, such as
`fetch_data("iris"; source="uci", version="1")`. Omit `source` for qualified
references and omit `version` when the reference embeds it. Without a version,
Datamonger uses the registry's declared default.

Pass a registry selector for one operation, or set it for the Julia session:

```julia
registry = BUNDLED_REGISTRY
iris = fetch_data("uci:iris@1"; registry=registry)

set_registry!(registry)
selected = active_registry()
set_registry!(nothing)
```

Pin a project's registry by checking its selector into
`.datamonger/selector.json`. Registry selection follows this order: a `registry`
keyword, a session setting from `set_registry!()`, the nearest project selector,
and the bundled registry.

Use `resolve_registry()` to discover a published release through the HTTPS
catalog. Record and reuse its release, index digest, and URL; looking up the
release name again is not a cryptographic pin. Registry updates are always
explicit. The [reproducibility guide](tutorials/reproducibility.md) includes a
project selector example and explains how to retain it with your analysis.

See the [trust model](https://github.com/jolars/datamonger/blob/main/TRUST.md)
for verification guarantees and their limits.

## Offline use and caching

Once a dataset is cached, reuse it without network access:

```julia
iris = fetch_data("uci:iris@1"; offline=true)
```

Offline mode keeps the same registry selection and requires valid cached files.
The bundled registry index is always available. Missing or corrupt cached
artifacts raise `OfflineError`; unavailable registry indexes raise
`RegistryOfflineError`.

Inspect the cache or remove the artifacts for a dataset version:

```julia
info = cache_info()
println(info.location, " ", info.total_size)
cache_clean(dataset="uci:iris@1")
```

`cache_clean()` also accepts an `older_than` duration, such as `Day(30)` from
`Dates`. Calling it without filters selects the entire cache. Entries in use by
another process are skipped, and Datamonger never evicts files automatically.
Pass `cache_dir` consistently to cache operations to use a custom location.

Julia manages native libraries separately in its artifact depot. Decoding does
not download executable code.

## Documentation

- [Julia documentation](https://datamonger.dev/packages/julia/)—guides and API
  reference.
- [Offline data workflow](tutorials/offline-workflow.md)—retrieval, missing
  values, sparse data, splits, and cache management.
- [Registries and reproducibility](tutorials/reproducibility.md)—dataset
  versions, selectors, and offline runs.
- [Dataset catalog](https://datamonger.dev/datasets/)—available datasets and
  retrieval examples.
- [Project repository](https://github.com/jolars/datamonger)—Python, R, and CLI
  clients, specifications, and architecture.

## Citation

If you use Datamonger in your research, please cite the release you used. Select
that release in the [Zenodo archive](https://doi.org/10.5281/zenodo.23692468)
and export its citation. To cite Datamonger generally, use the concept DOI
`10.5281/zenodo.23692468`.

Use `cite_data()` for dataset citations. Dataset metadata also preserves
upstream citation instructions and references.

## Contributing

See the [contributor
guide](https://github.com/jolars/datamonger/blob/main/CONTRIBUTING.md) for
development setup and how to add or revise datasets.

## License

Datamonger is licensed under the [MIT
license](https://github.com/jolars/datamonger/blob/main/LICENSE). Datasets
retain their own licenses and terms, recorded in their registry metadata.
