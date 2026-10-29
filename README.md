# Datamonger <img src="https://raw.githubusercontent.com/jolars/datamonger/refs/heads/main/assets/logo.png" align="right" width="139" alt="A datamonger carrying a box of data" />

[![CI](https://github.com/jolars/datamonger/actions/workflows/ci.yml/badge.svg)](https://github.com/jolars/datamonger/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/datamonger.svg?logo=python)](https://pypi.org/project/datamonger/)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23692468-blue)](https://doi.org/10.5281/zenodo.23692468)

Datamonger retrieves public research datasets in Python, R, and Julia. It
downloads and caches dataset files, returns native data frames and sparse
matrices, and verifies that each client decodes the same values. A standalone
CLI provides verified downloads for use with other tools.

Each dataset has a versioned record describing its source, format, provenance,
license, and citations. You can pin the registry and dataset version to keep an
analysis reproducible.

## Installation

From a repository checkout, install the client for your language.

### Python

Requires Python 3.11 or newer:

```console
python -m pip install ./packages/python
```

### R

Install the source package from R:

```r
install.packages("packages/r", repos = NULL, type = "source")
```

Source installation requires Cargo, Rust 1.82 or newer, and xz. See the [R
package guide](packages/r/README.md) for platform requirements.

### Julia

Activate and instantiate the package environment:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()
include("tools/dm_julia_core.jl")
```

### CLI

Download a prebuilt binary from [GitHub
releases](https://github.com/jolars/datamonger/releases), or install from the
checkout with Rust 1.89 or newer:

```console
cargo install --locked --path packages/cli
```

## Usage

Load a dataset by its `source:name` reference:

```python
from datamonger import fetch_data

iris = fetch_data("uci:iris")
heart = fetch_data("libsvm:heart_scale")
```

The same calls work in R:

```r
library(datamonger)

iris <- fetch_data("uci:iris")
heart <- fetch_data("libsvm:heart_scale")
```

And in Julia:

```julia
using Datamonger

iris = fetch_data("uci:iris")
heart = fetch_data("libsvm:heart_scale")
```

Delimited datasets return data frames. LIBSVM datasets return sparse features
and a response vector; datasets with train/test splits keep the two parts
separate. Files are downloaded on first use and kept in a verified local cache.
Offline mode lets you reuse cached datasets without network access.

Use `list_data()` to browse the registry, `data_info()` to inspect a dataset's
metadata, and `cite_data()` to retrieve its citations without downloading data:

```python
from datamonger import cite_data, data_info, list_data

datasets = list_data()
info = data_info("uci:iris")
print(cite_data("uci:iris"))
```

For raw files, use the CLI:

```console
datamonger list --source uci
datamonger info uci:iris
datamonger fetch uci:iris --output-dir ./data
```

The CLI verifies file sizes and SHA-256 hashes. It keeps the registered file
format and compression without decoding the data.

## Reproducibility

Select an explicit dataset version and retain the verification metadata with
your analysis:

```python
result = fetch_data("uci:iris@1", return_info=True)
print(result.info.dataset_id)
print(result.info.registry_release, result.info.registry_index_sha256)
```

Pin a project's registry by checking its selector into
`.datamonger/selector.json`. The selector records the registry release, index
digest, and retrieval URL. See the package guides for registry selection and
offline workflows, and the [trust model](TRUST.md) for the verification
guarantees and their limits.

<!-- bundled-registry:start -->
All four clients bundle the stable `1.4.0` snapshot. Its selector is
[`registry/releases/1.4.0/selector.json`](registry/releases/1.4.0/selector.json).
<!-- bundled-registry:end -->

Only the registry index is bundled; dataset files are downloaded separately.

## Documentation

- [Documentation website](https://datamonger.dev/)—guides and API references.
- [Python](packages/python/README.md), [R](packages/r/README.md), and
  [Julia](packages/julia/README.md) package guides—return types, metadata,
  registry selection, and cache management.
- [CLI guide](packages/cli/README.md)—commands and verified file downloads.
- [Specification](spec/README.md) and [architecture](DESIGN.md)—contracts and
  design rationale.

## Citation

If you use Datamonger in your research, please cite the release you used. Select
that release in the [Zenodo archive](https://doi.org/10.5281/zenodo.23692468)
and export its citation. To cite Datamonger generally, use the concept DOI
`10.5281/zenodo.23692468`.

Machine-readable metadata is available in [CITATION.cff](CITATION.cff).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and how to add or
revise datasets. Enter the repository's devenv shell and run the checks with:

```console
devenv test
```

## License

Datamonger is licensed under the [MIT license](LICENSE). Datasets retain their
own licenses and terms, recorded in their registry metadata.
