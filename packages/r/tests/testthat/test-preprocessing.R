test_that("preprocessing metadata follows the shared contract without changing data", {
  cache_dir <- tempfile("datamonger-preprocessing-")
  seeded <- seed_conformance_cache(cache_dir)
  cases <- read_fixture_json("conformance", "preprocessing.json")$cases
  baseline <- fetch_data("conformance:mixed_csv@1", registry = seeded$selector,
    cache_dir = cache_dir, offline = TRUE, return_info = TRUE)
  for (case in cases) {
    index <- seeded$index
    index$schema_version <- 3L
    index$datasets[[1]]$schema_version <- case$manifest_schema_version
    if ("preprocessing" %in% names(case)) {
      index$datasets[[1]]["preprocessing"] <- list(case$preprocessing)
    }
    transform <- identity
    if (identical(case$id, "empty-parameter-name")) {
      # jsonlite replaces empty list names when encoding; restore the malformed key.
      transform <- function(text) sub('"parameters":{"1":"value"}',
        '"parameters":{"":"value"}', text, fixed = TRUE)
    }
    options <- list(name = "conformance:mixed_csv@1",
      registry = reseal_index(index, cache_dir, transform),
      cache_dir = cache_dir, offline = TRUE)
    if (identical(case$expected, "invalid")) {
      expect_error(do.call(data_info, options),
        class = "datamonger_unsupported_registry", info = case$id)
      expect_error(do.call(fetch_data, options),
        class = "datamonger_unsupported_registry", info = case$id)
    } else {
      info <- do.call(data_info, options)
      result <- do.call(fetch_data, c(options, list(return_info = TRUE)))
      expect_identical(info$preprocessing, case$preprocessing, info = case$id)
      expect_identical(result$info$preprocessing, info$preprocessing, info = case$id)
      expect_identical(result$data, baseline$data, info = case$id)
      expect_identical(result$info$canonical_digest, baseline$info$canonical_digest,
        info = case$id)
      listed <- do.call(list_data, options[names(options) != "name"])
      expect_identical(listed[[1]]$preprocessing, info$preprocessing, info = case$id)
      cached <- cache_info(cache_dir)
      matching <- Filter(function(entry) identical(entry$sha256,
        options$registry$index_sha256), cached$entries)
      expect_identical(matching[[1]]$registry_release, options$registry$release,
        info = case$id)
    }
  }
})
