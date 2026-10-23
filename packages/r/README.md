# Datamonger

Datamonger brings public research datasets into R. It downloads and verifies the
data, returns data frames or sparse matrices, and keeps track of dataset
versions, sources, and citations. Downloaded files are cached for reuse,
including when you work offline.

## Installation

Datamonger is under development and is not yet on CRAN. Install the development
version from GitHub with pak:

```r
# install.packages("pak")
pak::pak("jolars/datamonger/packages/r")
```

Installation requires Rust, Cargo, and xz. On Windows, you also need Rtools and
the `x86_64-pc-windows-gnu` Rust target, which you can install with
`rustup target add x86_64-pc-windows-gnu`.

## Getting started

Fetch the Iris dataset from the UCI Machine Learning Repository:

```r
library(datamonger)

flowers <- fetch_data("uci:iris")
head(flowers)
```

The reference `"uci:iris"` combines the source and dataset name. You can also
write `fetch_data("iris", source = "uci")`. The first call downloads the data;
later calls verify and reuse the cached files.

Iris is returned as a data frame. Sparse datasets, such as those from LIBSVM,
return a sparse feature matrix and a response vector:

```r
heart <- fetch_data("libsvm:heart_scale")
dim(heart$features)
head(heart$response)
```

Datasets with predefined splits keep them separate. Access each split by name,
such as `data[["train"]]` or `data[["test"]]`.

## Find datasets

Browse the available datasets and inspect their metadata before downloading:

```r
list_data()

info <- data_info("uci:iris")
info
info$license
info$provenance
```

The package includes a dataset catalog, so these calls do not need to download
the data. Metadata includes the source, license, and known preprocessing steps.
Fetching a dataset does not apply the recorded preprocessing again.

To get citation text for your analysis:

```r
cat(cite_data("uci:iris"))
```

`cite_data()` includes upstream citation instructions and selects recommended
references when they are recorded. Use `include_all = TRUE` to see every
reference.

## Reproducible analyses

Add a version to a dataset reference to select it explicitly. Request metadata
alongside the data to record what you used:

```r
registry <- active_registry()
result <- fetch_data("uci:iris@1", registry = registry, return_info = TRUE)
flowers <- result$data
result$info

saveRDS(list(registry = registry, info = result$info), "iris-provenance.rds")
```

The metadata records the dataset version, catalog release, and checksums used to
verify the data. Save the registry selector with your analysis to reuse the same
catalog in a later session:

```r
provenance <- readRDS("iris-provenance.rds")
flowers <- fetch_data("uci:iris@1", registry = provenance$registry)
```

## Caching and offline use

After downloading a dataset, use it without network access:

```r
flowers <- fetch_data("uci:iris@1", offline = TRUE)
```

An offline fetch raises an error if a required file is missing from the cache.
Use `cache_info()` to inspect cached files and `cache_clean()` to remove them.
To use a separate cache for a project, pass `cache_dir`:

```r
flowers <- fetch_data("uci:iris@1", cache_dir = "data-cache")
cache_info(cache_dir = "data-cache")
```

## Learn more

See the [getting started vignette](vignettes/introduction.Rmd) for more
examples, or use `?fetch_data`, `?data_info`, and `?cite_data` in R. The
[project website](https://datamonger.dev) introduces the other Datamonger
clients, and [CONTRIBUTING.md](../../CONTRIBUTING.md) covers local development.

## License

Datamonger is licensed under the [MIT license](LICENSE). Datasets retain their
own licenses and terms; check each dataset's metadata before using it.
