# Datamonger <img src="https://raw.githubusercontent.com/jolars/datamonger/refs/heads/main/assets/logo.png" align="right" width="139" alt="A datamonger carrying a box of data" />

[![PyPI](https://img.shields.io/pypi/v/datamonger.svg?logo=python)](https://pypi.org/project/datamonger/)
[![CI](https://github.com/jolars/datamonger/actions/workflows/ci.yml/badge.svg)](https://github.com/jolars/datamonger/actions/workflows/ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23692468-blue)](https://doi.org/10.5281/zenodo.23692468)

Datamonger retrieves public research datasets in Python. It downloads and caches
dataset files, returns pandas data frames and SciPy sparse matrices, and
verifies that the decoded values match those in the registry. R and Julia
clients share the same registry and verification contracts.

Each dataset has a versioned record describing its source, format, provenance,
license, and citations. You can pin the registry and dataset version to keep an
analysis reproducible.

## Installation

Install from [PyPI](https://pypi.org/project/datamonger/) with Python 3.11 or
newer:

```console
python -m pip install datamonger
```

Prebuilt wheels are available for Linux, macOS, and Windows. Installing a wheel
requires no Rust compiler. Source builds require a stable Rust toolchain and a C
linker.

## Usage

Load a dataset by its `source:name` reference:

```python
from datamonger import fetch_data

iris = fetch_data("uci:iris")
heart = fetch_data("libsvm:heart_scale")
```

Delimited datasets return a `pandas.DataFrame`. LIBSVM datasets return a
`SparseDataset` with a SciPy CSR `features` matrix and a NumPy `response`
vector:

```python
print(iris.head())
print(heart.features.shape, heart.response.shape)
```

Datasets with train/test splits return a `SparseDatasetSplit` with separate
`train` and `test` fields. Datasets with provider-named splits return a
`DatasetSplits` mapping, accessed with keys such as `data["train"]` and
`data["validation"]`. Datamonger preserves each split's row membership.

Files are downloaded on first use and kept in a verified local cache. The
registry index is bundled with the package, so you can browse metadata without
network access. Dataset files are downloaded separately.

Use `list_data()` to browse the registry, `data_info()` to inspect a dataset's
metadata, and `cite_data()` to retrieve its citations without downloading data:

```python
from datamonger import cite_data, data_info, list_data

datasets = list_data()
info = data_info("uci:iris")
print(info.license)
print(cite_data("uci:iris"))
```

To retrieve a verified file without decoding it, use `fetch_artifact()`:

```python
from datamonger import fetch_artifact

iris_csv = fetch_artifact("uci:iris")
```

This returns a `pathlib.Path` in the cache. For datasets with several artifacts,
select one explicitly, for example with `artifact="train"`. Files retain their
registered format and compression.

## Reproducibility

Select an explicit dataset version and retain the verification metadata with
your analysis:

```python
result = fetch_data("uci:iris@1", return_info=True)
iris = result.data
print(result.info.dataset_id)
print(result.info.registry_release, result.info.registry_index_sha256)
print(result.info.canonical_digest)
```

`return_info=True` wraps the decoded data with its resolved identity, registry
selector, artifact digests, and decoded-verification record. Datamonger checks
artifact sizes and SHA-256 hashes, then verifies decoded shapes and a canonical
SHA-256 digest.

Dataset operations also accept separate arguments, such as
`fetch_data("iris", source="uci", version="1")`. Omit `source` for qualified
references and omit `version` when the reference embeds it. Without a version,
Datamonger uses the registry's declared default.

Pin a project's registry by checking its selector into
`.datamonger/selector.json`. To obtain a selector for a published release, use
an explicit catalog lookup:

```python
from datamonger import resolve_registry

registry = resolve_registry("1.4.0")
print(registry.release, registry.index_sha256, registry.index_url)
iris = fetch_data("uci:iris@1", registry=registry)
```

A project selector records those fields and a schema version:

```json
{
  "schema_version": 1,
  "release": "<registry.release>",
  "index_sha256": "<registry.index_sha256>",
  "index_url": "<registry.index_url>"
}
```

Replace the placeholders with the resolved values. Keep that selector with your
analysis; looking up the release name again is not a cryptographic pin.

Registry selection follows this order: a `registry=` argument, a session setting
from `set_registry()`, the nearest project selector, and the bundled registry.
Use `active_registry()` to inspect the current selection and
`set_registry(None)` to clear a session setting. Registry updates are always
explicit.

See the [trust model](https://github.com/jolars/datamonger/blob/main/TRUST.md)
for verification guarantees and their limits.

## Offline use and caching

Once a dataset is cached, reuse it without network access:

```python
iris = fetch_data("uci:iris@1", offline=True)
```

Offline mode keeps the same registry selection and requires valid cached files.
The bundled registry index is always available. Missing or corrupt cached
artifacts raise `OfflineError`; unavailable registry indexes raise
`RegistryOfflineError`. Both are exported from `datamonger.errors`.

Inspect the cache or remove the artifacts for a dataset version:

```python
from datamonger import cache_clean, cache_info

info = cache_info()
print(info.location, info.total_size)
cache_clean(dataset="uci:iris@1")
```

`cache_clean()` also accepts an `older_than` duration. Calling it without
filters selects the entire cache. Entries in use by another process are skipped,
and Datamonger never evicts files automatically. Pass `cache_dir=` consistently
to cache operations to use a custom location.

## Documentation

- [Documentation website](https://datamonger.dev/)—guides and API references.
- [Dataset catalog](https://datamonger.dev/datasets/)—available datasets and
  retrieval examples.
- [Project repository](https://github.com/jolars/datamonger)—R, Julia, and CLI
  clients, specifications, and architecture.
- [Changelog](https://github.com/jolars/datamonger/blob/main/packages/python/CHANGELOG.md)—Python
  client release notes.

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
development setup and how to add or revise datasets. To install from a
repository checkout, run this command from the repository root:

```console
python -m pip install ./packages/python
```

## License

Datamonger is licensed under the [MIT
license](https://github.com/jolars/datamonger/blob/main/LICENSE). Datasets
retain their own licenses and terms, recorded in their registry metadata.
