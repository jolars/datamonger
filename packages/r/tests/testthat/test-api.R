reseal_index <- function(index, cache_dir) {
  text <- jsonlite::toJSON(
    index,
    auto_unbox = TRUE,
    null = "null",
    digits = NA,
    pretty = FALSE
  )
  contents <- charToRaw(text)
  digest <- digest::digest(contents, algo = "sha256", serialize = FALSE)
  directory <- file.path(cache_dir, "registries", "sha256")
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  writeBin(contents, file.path(directory, digest))
  registry_selector(
    index$release,
    digest,
    "https://example.com/index.json"
  )
}

test_that("metadata operations expose identity and provenance without artifacts", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)

  info <- data_info(
    "mixed_csv",
    source = "conformance",
    registry = seeded$selector,
    cache_dir = cache_dir,
    offline = TRUE
  )
  listed <- list_data(
    registry = seeded$selector,
    cache_dir = cache_dir,
    offline = TRUE
  )

  expect_s3_class(info, "datamonger_data_info")
  expect_identical(info$dataset_id, "conformance:mixed_csv@1")
  expect_true(nzchar(info$provenance$provider))
  expect_length(listed, 5L)
  expect_true(all(vapply(listed, inherits, logical(1), "datamonger_data_info")))
})

test_that("decoded verification can be disabled only explicitly", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  result <- fetch_data(
    "mixed_csv",
    source = "conformance",
    registry = seeded$selector,
    cache_dir = cache_dir,
    offline = TRUE,
    verify_decoded = FALSE,
    return_info = TRUE
  )

  expect_identical(result$info$verification, "artifact")
  expect_null(result$info$canonical_form)
  expect_null(result$info$canonical_digest)
  expect_error(
    fetch_data(
      "mixed_csv",
      source = "conformance",
      registry = seeded$selector,
      cache_dir = cache_dir,
      offline = TRUE,
      verify_decoded = NA
    ),
    "must be TRUE or FALSE"
  )
})

test_that("public failures use the shared semantic taxonomy", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  expect_error(
    data_info(
      "missing",
      source = "conformance",
      registry = seeded$selector,
      cache_dir = cache_dir,
      offline = TRUE
    ),
    class = "datamonger_unknown_dataset"
  )

  index <- seeded$index
  index$datasets[[1]]$representation$decoder_version <- 2L
  unsupported <- reseal_index(index, cache_dir)
  expect_error(
    fetch_data(
      "mixed_csv",
      source = "conformance",
      registry = unsupported,
      cache_dir = cache_dir,
      offline = TRUE
    ),
    class = "datamonger_unsupported_decoder"
  )

  index <- seeded$index
  index$datasets[[1]]$artifacts[[1]]$distribution <- "metadata-only"
  index$datasets[[1]]$artifacts[[1]]$downloads <- NULL
  metadata_only <- reseal_index(index, cache_dir)
  expect_error(
    fetch_artifact(
      "mixed_csv",
      source = "conformance",
      registry = metadata_only,
      cache_dir = cache_dir,
      offline = TRUE
    ),
    class = "datamonger_artifact_unavailable"
  )

  index <- seeded$index
  index$datasets[[1]]$representation$expect$verification[[1]]$digest <- paste(rep("0", 64), collapse = "")
  mismatch <- reseal_index(index, cache_dir)
  expect_error(
    fetch_data(
      "mixed_csv",
      source = "conformance",
      registry = mismatch,
      cache_dir = cache_dir,
      offline = TRUE
    ),
    class = "datamonger_decoded_integrity"
  )
})

test_that("verification errata revoke records independent of JSON key order", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  index <- seeded$index
  dataset <- index$datasets[[1]]
  replacement <- dataset$representation$expect$verification[[1]]
  original <- list(
    canonical_form = 1L,
    algorithm = "sha256",
    digest = paste(rep("0", 64), collapse = "")
  )
  dataset$representation$expect$verification <- list(
    original,
    replacement
  )
  index$datasets[[1]] <- dataset
  index$errata <- list(list(
    schema_version = 1L,
    id = "mixed-csv-verification",
    release = "test-0001",
    dataset = list(
      name = dataset$name,
      version = dataset$version,
      source = dataset$source
    ),
    target = list(
      kind = "verification",
      canonical_form = 1L,
      algorithm = "sha256"
    ),
    original = list(
      algorithm = "sha256",
      digest = original$digest,
      canonical_form = 1L
    ),
    replacement = replacement,
    reason = "The earlier digest was incorrect.",
    approval = list(maintainer = "fixture", approved_at = "2026-09-07")
  ))
  selected <- reseal_index(index, cache_dir)

  result <- fetch_data(
    dataset$name,
    source = dataset$source,
    version = dataset$version,
    registry = selected,
    cache_dir = cache_dir,
    offline = TRUE,
    return_info = TRUE
  )

  expect_identical(result$info$canonical_digest, replacement$digest)
})
