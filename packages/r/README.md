# Datamonger R Client

This package implements Datamonger specification revision 1. It retrieves
artifacts through strongly selected immutable registry indexes, verifies their
bytes, decodes the revision 1 CSV, TSV, LIBSVM, and SVMLight representations,
and verifies the canonical logical digest.

The package is pre-release software and is not yet on CRAN. Install it from the
repository root:

```r
install.packages("packages/r", repos = NULL, type = "source")
```

Source installation requires Cargo and Rust 1.82 or newer, plus xz. The package
includes the Rust core and vendored dependencies, and compiles offline. Gzip and
bzip2 use Rust backends; no system zlib or libbz2 installation is required.
Windows source builds also require Rtools and the `x86_64-pc-windows-gnu` Rust
target, which can be installed with `rustup target add x86_64-pc-windows-gnu`.

The standalone `datamonger-core` library implements strict decoding and
canonical hashing. The R adapter constructs the documented R objects and keeps
registry selection, retrieval, caching, and metadata in R. Parsing reads input
incrementally, and verification hashes canonical bytes in bounded chunks.

## Cache

Datamonger uses the platform cache returned by `tools::R_user_dir()` by default.
Passing `cache_dir` uses that path for the call instead. For temporary caching,
create a session directory and pass it consistently:

```r
temporary_cache <- file.path(tempdir(), "datamonger", "r")
iris <- fetch_data("iris", source = "uci", cache_dir = temporary_cache)
```

The package never writes persistent files at installation or startup. Cache
growth is never automatic beyond explicitly requested registry and artifact
retrievals, eviction is manual through `cache_clean()`, and `cache_info()`
reports every content-addressed entry. Datamonger performs no telemetry.

## Use

The bundled stable index is the default trust root. Its dataset artifacts are
retrieved on first use:

```r
library(datamonger)

iris <- fetch_data("iris", source = "uci")
heart <- fetch_data("heart_scale", source = "libsvm")
```

`fetch_data()`, `data_info()`, and `fetch_artifact()` also accept the dataset
references used by the CLI:

```r
iris <- fetch_data("uci:iris")
iris_v1 <- fetch_data("uci:iris@1")
iris_v1 <- fetch_data("uci:iris", version = "1")
```

A bare name requires `source`. Omit `source` for qualified references, and omit
`version` when the reference embeds it. Duplicate arguments raise an error even
when the values agree. An omitted version selects the registry's declared
default.

For reproducible analysis, select an explicit version and retain the returned
metadata:

```r
result <- fetch_data(
  "iris",
  source = "uci",
  version = "1",
  return_info = TRUE
)
result$info$dataset_id
result$info$registry_release
result$info$registry_index_sha256
result$info$canonical_digest
```

Delimited data are returned as a data frame. Exact `int64` columns use the
`datamonger_int64` vector class, backed by canonical decimal strings; this
represents the full signed 64-bit range without conflating its minimum value
with missing data. LIBSVM data return a `datamonger_sparse_dataset` containing a
row-compressed `Matrix` feature matrix and an exact response vector. When a
dimension or stored-value count exceeds the `Matrix` package's integer limit,
the feature matrix is an exact `datamonger_csr_matrix` instead. Split
representations keep `train` and `test` datasets separate.

The `named-splits` assembly returns a `datamonger_dataset_splits` named list in
recipe order. Access provider splits as `data[["train"]]`,
`data[["validation"]]`, or `data[["test"]]`. Each value is a table or sparse
dataset, and feature-only tables omit responses. The [named splits
contract](../../spec/decoders/named-splits-v1.md) requires manifest schema 4 and
preserves each split's original name and row membership.

`data_info()` and `list_data()` inspect provenance, license, distribution, and
task metadata without retrieving artifacts. `fetch_artifact()` retrieves only
verified artifact bytes. `offline = TRUE` forbids network access and requires
the selected index and artifacts to be bundled or already cached.

`data_info(...)$preprocessing` and fetch results requested with
`return_info = TRUE` expose upstream and Datamonger processing in version 3
registries. Each stage distinguishes `unknown`, `none`, and `documented` and
preserves known steps, string parameters, and evidence references. Missing
metadata is `NULL`, including in older bundled snapshots. Fetching does not
apply the described transformations. See the [preprocessing
contract](../../spec/preprocessing.md).

The [getting started vignette](vignettes/introduction.Rmd) introduces dataset
discovery, retrieval, citations, reproducibility, and caching with public
research datasets. Metadata examples run offline; examples that download data
are shown without being evaluated during the build.

## Registry selection

An explicit strong selector fixes the release and exact index bytes:

```r
selected <- registry_selector(
  release = "2026.08",
  index_sha256 = paste0(rep("0", 64), collapse = ""),
  index_url = "https://registry.example/2026.08/index.json"
)
```

Selection precedence is a per-call `registry` argument, `set_registry()` for the
session, the nearest `.datamonger/selector.json`, and the bundled selector.
`resolve_registry()` discovers a selector by bare release through a mutable
HTTPS catalog. That lookup is trusted only as strongly as the TLS session; it is
not a cryptographic pin until its returned release and digest are recorded and
reused.

The project code is MIT-licensed. Datasets retain their own licenses and terms;
registry inclusion is not a license grant or a preservation guarantee.

## Dataset citations

`cite_data("uci:wine-quality@1")` returns curated citation text without
retrieving dataset artifacts. Use `format = "records"` for reference records and
`include_all = TRUE` to include every reference. A reference may have a
`dataset`, `paper`, or `collection` role, a note, and an upstream recommendation
flag. Multiple references can be recommended together. Roles do not imply
recommendations.

By default, references marked as recommended are selected. If no recommendation
flags are recorded, all references are returned and text output explains that
the recommendation is unknown. Missing citations produce an empty list of
records or an explicit text message. Legacy single citations remain supported.

`data_info(...)$citations` and
`fetch_data(..., return_info = TRUE)$info$citations` contain every reference
from the selected registry record. `citation_instructions` preserves upstream
instructions, including requests to cite several references together. No
bibliographic lookups are performed.
