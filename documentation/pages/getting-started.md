# Getting started

Choose Python, R, or Julia to load the Iris dataset into a data frame, or use
the command-line tool to download its original file. All four clients bundle a
registry snapshot. The first download needs network access.

## Python

Install from GitHub with Python 3.11 or newer. The source build requires Git,
a stable Rust toolchain, and a C linker.

```console
python -m pip install "git+https://github.com/jolars/datamonger.git#subdirectory=packages/python"
```

```python
from datamonger import data_info, fetch_data

info = data_info("uci:iris@1")
iris = fetch_data("uci:iris@1")
```

See the [Python API reference](../package-pages/python/index.md).

## R

Install from GitHub with pak. The source build requires Cargo, Rust 1.82 or
newer, and xz. See the [R package guide](https://github.com/jolars/datamonger/blob/main/packages/r/README.md)
for platform requirements.

```r
# install.packages("pak")
pak::pak("jolars/datamonger/packages/r")
```

```r
library(datamonger)

info <- data_info("uci:iris@1")
iris <- fetch_data("uci:iris@1")
```

See the [R vignette](../../packages/r/vignettes/introduction.Rmd) for dataset
discovery, citations, and offline use.

## Julia

Install from GitHub into your active environment with Julia 1.10 or newer.

```julia
using Pkg
Pkg.add(url="https://github.com/jolars/datamonger.git", subdir="packages/julia")
```

```julia
using Datamonger

info = data_info("uci:iris@1")
iris = fetch_data("uci:iris@1")
```

See the [Julia API reference](../package-pages/julia/index.md) or follow the
[offline data workflow](../../packages/julia/tutorials/offline-workflow.md).

## Command line

Install the prebuilt CLI on supported Linux and macOS systems.

```sh
curl --proto '=https' --tlsv1.2 -LsSf https://datamonger.dev/install | sh
```

You can also download a binary from [GitHub Releases](https://github.com/jolars/datamonger/releases)
or install from crates.io with Rust 1.89 or newer.

```console
cargo install datamonger --locked
```

List datasets, inspect the Iris record, and download the verified file.

```console
datamonger list --source uci
datamonger info uci:iris@1
datamonger fetch uci:iris@1 --output-dir ./data
```

The CLI preserves the registered file format and compression. It refuses to
overwrite an existing export. See the [command-line reference](cli-reference.md)
for all commands and options.

## Dataset versions and reproducibility

The [dataset catalog](../generated/datasets/index.md) lists valid references and
gives retrieval examples. A reference such as `uci:iris` selects the default
version in the active registry. Add `@1` to request version 1 explicitly.

To reproduce data access, record the dataset version and pin the registry with
a selector in `.datamonger/selector.json` at the root of your project. The
selector records the registry release, index digest, and retrieval URL. See the
[registries and reproducibility guide](../../packages/julia/tutorials/reproducibility.md)
for details.
