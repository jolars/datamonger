test_that("all delimited and LIBSVM cases match shared golden digests", {
  document <- read_fixture_json("conformance", "cases.json")
  expect_identical(document$schema_version, 1L)
  expect_identical(document$canonical_form, 1L)

  for (case in document$cases) {
    recipe <- case$recipe
    decoded <- switch(
      case$decoder,
      `delimited-text` = dm_internal(".decode_delimited")(
        fixture_path("conformance", case$input), recipe
      ),
      libsvm = dm_internal(".decode_libsvm")(
        fixture_path("conformance", case$input), recipe
      ),
      `libsvm-split` = dm_internal(".decode_libsvm_split")(
        fixture_path("conformance", case$input$train),
        fixture_path("conformance", case$input$test),
        recipe
      )
    )
    actual <- dm_internal(".canonical_sha256")(decoded$components)
    expect_identical(actual, case$expected_sha256, info = case$id)
  }
})

test_that("canonical value cases have exact bytes", {
  document <- read_fixture_json("conformance", "canonical", "cases.json")

  for (case in document$cases) {
    component <- dm_internal(".component_from_descriptor")(case$component)
    actual <- dm_internal(".canonical_bytes")(list(component))
    expect_identical(
      paste(format(actual), collapse = ""),
      case$expected_hex,
      info = case$id
    )
  }
})

test_that("shared malformed and fuzz cases are decode errors", {
  malformed <- read_fixture_json("conformance", "malformed.json")$cases
  for (case in malformed) {
    run <- function() {
      switch(
        case$decoder,
        `delimited-text` = dm_internal(".decode_delimited")(
          fixture_path("conformance", case$input), case$recipe
        ),
        libsvm = dm_internal(".decode_libsvm")(
          fixture_path("conformance", case$input), case$recipe
        ),
        `libsvm-split` = dm_internal(".decode_libsvm_split")(
          fixture_path("conformance", case$input$train),
          fixture_path("conformance", case$input$test),
          case$recipe
        )
      )
    }
    expect_error(run(), class = "datamonger_decode", info = case$id)
  }

  fuzz <- read_fixture_json("conformance", "fuzz-regressions.json")$cases
  csv_recipe <- read_fixture_json("conformance", "cases.json")$cases[[1]]$recipe
  csv_recipe$columns <- list(list(name = "x", type = "string"))
  svm_recipe <- read_fixture_json("conformance", "cases.json")$cases[[3]]$recipe
  for (case in fuzz) {
    path <- tempfile()
    writeBin(dm_internal(".hex_to_raw")(case$input_hex), path)
    on.exit(unlink(path), add = TRUE)
    run <- if (case$decoder == "delimited-text") {
      function() dm_internal(".decode_delimited")(path, csv_recipe)
    } else {
      function() dm_internal(".decode_libsvm")(path, svm_recipe)
    }
    expect_error(run(), class = "datamonger_decode", info = case$id)
  }
})

test_that("the public API round-trips every test-registry representation", {
  cache_dir <- tempfile("datamonger-cache-")
  seeded <- seed_conformance_cache(cache_dir)
  cases <- read_fixture_json("conformance", "cases.json")$cases
  expected <- stats::setNames(
    vapply(cases, `[[`, character(1), "expected_sha256"),
    vapply(cases, `[[`, character(1), "dataset")
  )

  for (dataset in seeded$index$datasets) {
    result <- fetch_data(
      dataset$name,
      source = dataset$source,
      version = dataset$version,
      registry = seeded$selector,
      cache_dir = cache_dir,
      offline = TRUE,
      return_info = TRUE
    )
    id <- paste0(dataset$source, ":", dataset$name, "@", dataset$version)
    expect_s3_class(result, "datamonger_fetch_result")
    expect_identical(result$info$verification, "decoded")
    expect_identical(result$info$canonical_digest, unname(expected[[id]]))
  }
})
