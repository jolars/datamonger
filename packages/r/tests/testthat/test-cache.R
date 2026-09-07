cache_object <- function(cache_dir, namespace, contents) {
  digest <- digest::digest(contents, algo = "sha256", serialize = FALSE)
  directory <- file.path(cache_dir, namespace, "sha256")
  dir.create(directory, recursive = TRUE, showWarnings = FALSE)
  path <- file.path(directory, digest)
  writeBin(contents, path)
  list(path = path, digest = digest)
}

test_that("cache inventory verifies entries and manual cleaning is selective", {
  cache_dir <- tempfile("datamonger-cache-")
  object <- cache_object(cache_dir, "objects", charToRaw("artifact"))
  corrupt <- cache_object(cache_dir, "objects", charToRaw("other"))
  writeBin(charToRaw("corrupt"), corrupt$path)

  info <- cache_info(cache_dir)

  expect_s3_class(info, "datamonger_cache_info")
  expect_identical(info$total_size, 15)
  expect_setequal(
    vapply(info$entries, `[[`, character(1), "sha256"),
    c(object$digest, corrupt$digest)
  )
  validity <- stats::setNames(
    vapply(info$entries, `[[`, logical(1), "valid"),
    vapply(info$entries, `[[`, character(1), "sha256")
  )
  expect_true(validity[[object$digest]])
  expect_false(validity[[corrupt$digest]])

  result <- cache_clean(older_than = 0, cache_dir = cache_dir)
  expect_length(result$removed, 2L)
  expect_identical(result$bytes_removed, 15)
  expect_false(file.exists(object$path))
})

test_that("cleaners skip objects held by a reader or publisher", {
  cache_dir <- tempfile("datamonger-cache-")
  object <- cache_object(cache_dir, "objects", charToRaw("active"))
  lease <- dm_internal(".acquire_lock")(
    dm_internal(".lease_path")(cache_dir, "objects", object$digest),
    exclusive = FALSE
  )
  on.exit(dm_internal(".release_lock")(lease), add = TRUE)

  result <- cache_clean(cache_dir = cache_dir)

  expect_length(result$removed, 0L)
  expect_length(result$skipped, 1L)
  expect_true(file.exists(object$path))
})

test_that("publication falls back after bad bytes and caches only valid bytes", {
  cache_dir <- tempfile("datamonger-cache-")
  expected <- charToRaw("expected")
  digest <- digest::digest(expected, algo = "sha256", serialize = FALSE)
  requested <- character()
  testthat::local_mocked_bindings(
    .download_url_to_file = function(url, path, require_https = FALSE) {
      requested <<- c(requested, url)
      writeBin(if (endsWith(url, "bad")) charToRaw("bad") else expected, path)
      invisible(path)
    },
    .package = "datamonger"
  )

  leased <- dm_internal(".retrieve_cached_object")(
    cache_dir,
    "objects",
    digest,
    length(expected),
    c("https://example.com/bad", "https://example.com/good"),
    FALSE,
    "datamonger_artifact_integrity",
    "datamonger_artifact_offline",
    "datamonger_retrieval_exhausted"
  )
  on.exit(dm_internal(".release_lock")(leased$lease), add = TRUE)

  expect_identical(requested, c("https://example.com/bad", "https://example.com/good"))
  expect_identical(readBin(leased$path, "raw", n = 100), expected)
})

test_that("complete mismatched downloads end as artifact-integrity failures", {
  cache_dir <- tempfile("datamonger-cache-")
  digest <- paste(rep("a", 64), collapse = "")
  testthat::local_mocked_bindings(
    .download_url_to_file = function(url, path, require_https = FALSE) {
      writeBin(charToRaw("wrong"), path)
      invisible(path)
    },
    .package = "datamonger"
  )

  expect_error(
    dm_internal(".retrieve_cached_object")(
      cache_dir,
      "objects",
      digest,
      5,
      c("https://example.com/one", "https://example.com/two"),
      FALSE,
      "datamonger_artifact_integrity",
      "datamonger_artifact_offline",
      "datamonger_retrieval_exhausted"
    ),
    class = "datamonger_artifact_integrity"
  )
  expect_false(file.exists(file.path(cache_dir, "objects", "sha256", digest)))
})

test_that("offline and exhausted retrieval have distinct semantic classes", {
  cache_dir <- tempfile("datamonger-cache-")
  digest <- paste(rep("a", 64), collapse = "")
  expect_error(
    dm_internal(".retrieve_cached_object")(
      cache_dir,
      "objects",
      digest,
      1,
      "https://example.com/missing",
      TRUE,
      "datamonger_artifact_integrity",
      "datamonger_artifact_offline",
      "datamonger_retrieval_exhausted"
    ),
    class = "datamonger_artifact_offline"
  )

  testthat::local_mocked_bindings(
    .download_url_to_file = function(...) {
      dm_internal(".dm_abort")(
        "datamonger_retrieval_exhausted",
        "transport failed"
      )
    },
    .package = "datamonger"
  )
  expect_error(
    dm_internal(".retrieve_cached_object")(
      cache_dir,
      "objects",
      digest,
      1,
      "https://example.com/missing",
      FALSE,
      "datamonger_artifact_integrity",
      "datamonger_artifact_offline",
      "datamonger_retrieval_exhausted"
    ),
    class = "datamonger_retrieval_exhausted"
  )
})

test_that("HTTP gzip decoding rejects concatenated content", {
  first <- compress_fixture(write_text("first"), "gzip")
  second <- compress_fixture(write_text("second"), "gzip")
  first_bytes <- readBin(first, "raw", n = file.info(first)$size)
  expect_identical(
    dm_internal(".decode_http_gzip")(
      first_bytes,
      "https://example.com/data"
    ),
    charToRaw("first")
  )
  concatenated <- c(
    first_bytes,
    readBin(second, "raw", n = file.info(second)$size)
  )
  expect_error(
    dm_internal(".decode_http_gzip")(concatenated, "https://example.com/data"),
    class = "datamonger_retrieval_exhausted"
  )
  identical_members <- c(
    first_bytes,
    first_bytes
  )
  expect_error(
    dm_internal(".decode_http_gzip")(
      identical_members,
      "https://example.com/data"
    ),
    class = "datamonger_retrieval_exhausted"
  )
  trailing <- c(first_bytes, as.raw(0))
  expect_error(
    dm_internal(".decode_http_gzip")(trailing, "https://example.com/data"),
    class = "datamonger_retrieval_exhausted"
  )
  expect_error(
    dm_internal(".decode_http_gzip")(head(first_bytes, -1L), "https://example.com/data"),
    class = "datamonger_retrieval_exhausted"
  )
})
