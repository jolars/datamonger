test_that("fetch_data verifies native results without serializing them in R", {
  cache_dir <- tempfile("datamonger-native-")
  on.exit(unlink(cache_dir, recursive = TRUE), add = TRUE)
  seeded <- seed_conformance_cache(cache_dir)
  cases <- read_fixture_json("conformance", "cases.json")$cases
  testthat::with_mocked_bindings(
    {
      for (case in cases) {
        result <- fetch_data(
          case$dataset, registry = seeded$selector, cache_dir = cache_dir,
          offline = TRUE, return_info = TRUE
        )
        expect_identical(result$info$canonical_digest, case$expected_sha256)
        expect_identical(result$info$verification, "decoded")
        unverified <- fetch_data(
          case$dataset, registry = seeded$selector, cache_dir = cache_dir,
          offline = TRUE, verify_decoded = FALSE, return_info = TRUE
        )
        expect_identical(unverified$info$verification, "artifact")
        expect_null(unverified$info$canonical_digest)
      }
    },
    .canonical_bytes = function(...) stop("Production must hash in Rust"),
    .canonical_sha256 = function(...) stop("Production must hash before conversion"),
    .package = "datamonger"
  )
})

test_that("native gzip failures retain retrieval error classes", {
  path <- compress_fixture(write_text("verified bytes"), "gzip")
  on.exit(unlink(path), add = TRUE)
  contents <- readBin(path, "raw", n = file.info(path)$size)
  contents[[length(contents) - 7L]] <- as.raw(bitwXor(
    as.integer(contents[[length(contents) - 7L]]), 1L
  ))
  expect_error(
    dm_internal(".decode_http_gzip")(contents, "https://example.com/data"),
    class = "datamonger_retrieval_exhausted"
  )
})

test_that("inaccessible artifact files retain the cache error class", {
  expect_error(
    dm_internal(".decode_libsvm")(tempfile(), conformance_recipe(3)),
    class = "datamonger_cache"
  )
})

test_that("native cancellation becomes an interrupt after returning to R", {
  condition <- tryCatch(
    dm_internal(".native_result")(list(
      category = "interrupted", message = "interrupted"
    )),
    interrupt = identity
  )
  expect_s3_class(condition, "interrupt")
  expect_identical(conditionMessage(condition), "interrupted")
})

test_that("R rejects strings that its runtime cannot represent", {
  recipe <- conformance_recipe(1)
  recipe$columns <- list(list(name = "x", type = "string"))
  path <- write_bytes(as.raw(c(0x78, 0x0a, 0x61, 0x00, 0x62, 0x0a)))
  on.exit(unlink(path), add = TRUE)
  expect_error(
    dm_internal(".decode_delimited")(path, recipe),
    class = "datamonger_decode"
  )
})
