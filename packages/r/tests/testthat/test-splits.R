seed_split_case <- function(case, cache_dir, compression = "none") {
  dataset <- case$manifest
  directory <- file.path(cache_dir, "objects", "sha256")
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  for (i in seq_along(dataset$artifacts)) {
    artifact <- dataset$artifacts[[i]]
    path <- fixture_path("conformance", case$artifact_paths[[artifact$name]])
    if (!identical(compression, "none")) path <- compress_fixture(path, compression)
    contents <- readBin(path, "raw", n = file.info(path)$size)
    artifact$compression <- compression
    artifact$size <- length(contents)
    artifact$sha256 <- digest::digest(contents, algo = "sha256", serialize = FALSE)
    writeBin(contents, file.path(directory, artifact$sha256))
    dataset$artifacts[[i]] <- artifact
  }
  index <- list(schema_version = 4L, release = "named-splits-test", datasets = list(dataset), defaults = list())
  reseal_index(index, cache_dir)
}

test_that("named splits preserve provider names, membership, and absent labels", {
  document <- read_fixture_json("conformance", "named-splits.json")
  for (case in document$cases) {
    for (compression in c("none", "gzip", "bzip2")) {
      cache_dir <- tempfile("datamonger-splits-")
      registry <- seed_split_case(case, cache_dir, compression)
      result <- fetch_data(paste0("conformance:", case$id, "@1"), registry = registry,
        cache_dir = cache_dir, offline = TRUE, return_info = TRUE)
      expect_s3_class(result$data, "datamonger_dataset_splits")
      expect_identical(names(result$data), vapply(case$expected_splits, `[[`, character(1), "name"))
      expected_bytes <- as.raw(strtoi(substring(case$expected_hex,
        seq(1L, nchar(case$expected_hex), 2L), seq(2L, nchar(case$expected_hex), 2L)), 16L))
      expect_identical(result$info$canonical_digest,
        digest::digest(expected_bytes, algo = "sha256", serialize = FALSE))
      expect_identical(result$info$verification, "decoded")
      expect_setequal(names(result$info$artifact_digests), names(case$artifact_paths))
      unchecked <- fetch_data(paste0("conformance:", case$id, "@1"), registry = registry,
        cache_dir = cache_dir, offline = TRUE, verify_decoded = FALSE, return_info = TRUE)
      expect_identical(unchecked$data, result$data)
      expect_identical(unchecked$info$verification, "artifact")
      expect_null(unchecked$info$canonical_digest)
      for (expected in case$expected_splits) {
        split <- result$data[[expected$name]]
        if (identical(expected$kind, "sparse")) {
          expect_s3_class(split, "datamonger_sparse_dataset")
          expect_equal(unname(as.matrix(split$features)), do.call(rbind, lapply(expected$features, unlist)))
          expect_equal(as.numeric(split$response), unlist(expected$response))
        } else {
          expect_s3_class(split, "data.frame")
          expect_identical(names(split), unlist(expected$columns))
          for (column in names(split)) {
            expect_equal(as.numeric(split[[column]]), as.numeric(unlist(expected$values[[column]])))
          }
        }
      }
      setup <- dm_internal(".validate_representation")(case$manifest)
      paths <- vapply(case$manifest$artifacts, function(artifact) {
        fixture_path("conformance", case$artifact_paths[[artifact$name]])
      }, character(1))
      decoded <- dm_internal(".decode_setup")(setup, paths, FALSE)
      expect_identical(dm_internal(".canonical_bytes")(decoded$components), expected_bytes)
    }
  }
})

test_that("invalid named split recipes use the shared failure category", {
  document <- read_fixture_json("conformance", "named-splits.json")
  for (invalid in document$invalid) {
    case <- document$cases[[1]]
    case$manifest$representation <- invalid$representation
    cache_dir <- tempfile("datamonger-invalid-split-")
    registry <- seed_split_case(case, cache_dir)
    expect_error(fetch_data("conformance:three-provider-splits@1", registry = registry,
      cache_dir = cache_dir, offline = TRUE), class = "datamonger_unsupported_decoder", info = invalid$id)
  }
})

test_that("named split verification detects reassigned membership and order", {
  for (mutation in c("order", "membership")) {
    case <- read_fixture_json("conformance", "named-splits.json")$cases[[1]]
    if (identical(mutation, "order")) {
      case$manifest$representation$options$splits <- rev(case$manifest$representation$options$splits)
    } else {
      case$manifest$representation$inputs$validation <- case$manifest$representation$inputs$train
    }
    cache_dir <- tempfile("datamonger-changed-split-")
    registry <- seed_split_case(case, cache_dir)
    expect_error(fetch_data("conformance:three-provider-splits@1", registry = registry,
      cache_dir = cache_dir, offline = TRUE), class = "datamonger_decoded_integrity")
  }
})
