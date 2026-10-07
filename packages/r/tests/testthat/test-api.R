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

test_that("dataset references select the same data, artifacts, and metadata", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  selections <- list(
    list(name = "mixed_csv", source = "conformance"),
    list(name = "conformance:mixed_csv"),
    list(name = "conformance:mixed_csv", version = "1"),
    list(name = "conformance:mixed_csv@1")
  )
  for (selection in selections) {
    arguments <- c(selection, list(
      registry = seeded$selector, cache_dir = cache_dir, offline = TRUE
    ))
    info <- do.call(data_info, arguments)
    result <- do.call(fetch_data, c(arguments, list(return_info = TRUE)))
    artifact <- do.call(fetch_artifact, arguments)
    expect_identical(info$dataset_id, "conformance:mixed_csv@1")
    expect_identical(result$info$dataset_id, info$dataset_id)
    expect_identical(info$source, "conformance")
    expect_identical(info$name, "mixed_csv")
    expect_identical(info$version, "1")
    expect_identical(result$info$verification, "decoded")
    expect_identical(dim(result$data), c(5L, 4L))
    expect_identical(
      digest::digest(file = artifact, algo = "sha256"),
      info$artifacts[[1]]$sha256
    )
  }
})

test_that("ambiguous arguments fail before registry loading", {
  registry <- registry_selector(
    "uncached", paste(rep("0", 64), collapse = ""), "https://example.invalid/index"
  )
  selections <- list(
    list(name = "mixed_csv"),
    list(name = "conformance:mixed_csv", source = "conformance"),
    list(name = "conformance:mixed_csv", source = "other"),
    list(name = "conformance:mixed_csv@1", version = "1"),
    list(name = "conformance:mixed_csv@1", version = "2")
  )
  for (operation in list(fetch_data, data_info, fetch_artifact)) {
    for (selection in selections) {
      cache_dir <- tempfile("datamonger-cache-")
      expect_error(
        do.call(operation, c(selection, list(
          registry = registry, cache_dir = cache_dir, offline = TRUE
        ))),
        "source|version"
      )
      expect_false(dir.exists(cache_dir))
    }
  }
})

test_that("malformed references fail as unknown datasets", {
  registry <- registry_selector(
    "uncached", paste(rep("0", 64), collapse = ""), "https://example.invalid/index"
  )
  references <- c(
    ":mixed_csv", "conformance:", "conformance:mixed_csv@",
    "conformance:mixed_csv@1@2", "conformance:other:mixed_csv",
    " conformance:mixed_csv", "conformance:mixed_csv\n",
    "Conformance:mixed_csv", "conformance:mixed/csv", "mixed_csv@1"
  )
  for (operation in list(fetch_data, data_info, fetch_artifact)) {
    for (reference in references) {
      expect_error(
        operation(reference, registry = registry, cache_dir = tempfile(), offline = TRUE),
        class = "datamonger_unknown_dataset"
      )
    }
  }
})

test_that("qualified references preserve resolution errors", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  for (reference in c("conformance:missing", "conformance:mixed_csv@2")) {
    expect_error(
      data_info(
        reference, registry = seeded$selector, cache_dir = cache_dir, offline = TRUE
      ),
      class = "datamonger_unknown_dataset"
    )
  }
})

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
