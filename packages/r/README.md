# Datamonger R client

This package implements Datamonger specification release candidate
`spec-v1-rc1`. It retrieves artifacts through strongly selected immutable
registry indexes, verifies their bytes, decodes the revision 1 CSV, TSV,
LIBSVM, and SVMLight representations, and verifies the canonical logical
digest.

The package is pre-release software and is not yet on CRAN. Install it from the
repository root:

```r
install.packages("packages/r", repos = NULL, type = "source")
```

## Cache consent

Passing `cache_dir` gives Datamonger permission to use that path for the call.
Without it, Datamonger asks once before using the platform cache returned by
`tools::R_user_dir()` in an interactive session. If consent is absent or
declined, it uses a directory under `tempdir()`.

For non-interactive work, configure the choice explicitly:

```r
options(datamonger.cache_consent = TRUE)  # Persistent user cache.
options(datamonger.cache_consent = FALSE) # Session-temporary cache.
```

The package never writes persistent files at installation or startup. Cache
growth is never automatic beyond explicitly requested registry and artifact
retrievals, eviction is manual through `cache_clean()`, and `cache_info()`
reports every content-addressed entry. Datamonger performs no telemetry.

## Use

The bundled `proof-0001` index is the default trust root. Its dataset artifacts
are retrieved on first use:

```r
library(datamonger)

options(datamonger.cache_consent = TRUE)
iris <- fetch_data("iris", source = "uci")
heart <- fetch_data("heart_scale", source = "libsvm")
```

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
with missing data. LIBSVM data return a `datamonger_sparse_dataset` containing
a row-compressed `Matrix` feature matrix and an exact response vector. When a
declared dimension exceeds the `Matrix` package's integer limit, the feature
matrix is an exact `datamonger_csr_matrix` instead. Split representations keep
`train` and `test` datasets separate.

`data_info()` and `list_data()` inspect provenance, license, distribution, and
task metadata without retrieving artifacts. `fetch_artifact()` retrieves only
verified artifact bytes. `offline = TRUE` forbids network access and requires
the selected index and artifacts to be bundled or already cached.

## Registry selection

An explicit strong selector fixes the release and exact index bytes:

```r
selected <- registry_selector(
  release = "2026.08",
  index_sha256 = paste0(rep("0", 64), collapse = ""),
  index_url = "https://registry.example/2026.08/index.json"
)
```

Selection precedence is a per-call `registry` argument, `set_registry()` for
the session, the nearest `.datamonger/selector.json`, and the bundled selector.
`resolve_registry()` discovers a selector by bare release through a mutable
HTTPS catalog. That lookup is trusted only as strongly as the TLS session; it
is not a cryptographic pin until its returned release and digest are recorded
and reused.

The project code is MIT-licensed. Datasets retain their own licenses and terms;
registry inclusion is not a license grant or a preservation guarantee.
