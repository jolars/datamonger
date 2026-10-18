test_that("citations preserve roles, instructions, and upstream recommendations", {
  cache_dir <- tempfile("datamonger-citations-")
  seeded <- seed_conformance_cache(cache_dir)
  index <- seeded$index
  index$schema_version <- 2L
  index$datasets[[1]]$schema_version <- 2L
  records <- list(
    list(citation = "Dataset deposit.", role = "dataset", recommended = TRUE),
    list(citation = "Collection paper.", role = "paper", recommended = TRUE,
      note = "Describes the observations."),
    list(citation = "Benchmark collection.", role = "collection", recommended = FALSE),
    list(citation = "Other reference.")
  )
  index$datasets[[1]]$provenance$citations <- records
  index$datasets[[1]]$provenance$citation_instructions <- "Please cite both references."
  selector <- reseal_index(index, cache_dir)
  options <- list(name = "conformance:mixed_csv@1", registry = selector,
    cache_dir = cache_dir, offline = TRUE)
  info <- do.call(data_info, options)
  result <- do.call(fetch_data, c(options, list(return_info = TRUE)))
  expect_identical(info$citations, records)
  expect_identical(result$info$citations, records)
  expect_identical(result$info$citation_instructions, info$citation_instructions)
  expect_identical(result$info$registry_index_sha256, selector$index_sha256)
  cached <- cache_info(cache_dir)
  matching <- Filter(function(x) identical(x$sha256, selector$index_sha256), cached$entries)
  expect_identical(matching[[1]]$registry_release, selector$release)
  expect_identical(do.call(cite_data, c(options, list(format = "records"))), records[1:2])
  expect_identical(do.call(cite_data, c(options, list(format = "records", include_all = TRUE))), records)
  text <- do.call(cite_data, options)
  expect_match(text, "Please cite both references.", fixed = TRUE)
  expect_match(text, "[dataset] Dataset deposit.", fixed = TRUE)
  expect_match(text, "Describes the observations.", fixed = TRUE)
  expect_false(grepl("Benchmark", text))

  unlink(file.path(cache_dir, "objects"), recursive = TRUE)
  expect_identical(do.call(cite_data, options), text)

  index$datasets[[1]]$provenance$citations <- NULL
  index$datasets[[1]]$provenance$citation_instructions <- NULL
  index$datasets[[1]]$schema_version <- 1L
  index$datasets[[1]]$provenance$citation <- "Legacy reference."
  options$registry <- reseal_index(index, cache_dir)
  expect_identical(do.call(cite_data, c(options, list(format = "records"))),
    list(list(citation = "Legacy reference.")))
  expect_match(do.call(cite_data, options), "No upstream citation recommendation", fixed = TRUE)

  index$datasets[[1]]$provenance$citation <- NULL
  options$registry <- reseal_index(index, cache_dir)
  expect_identical(do.call(cite_data, c(options, list(format = "records"))), list())
  expect_identical(do.call(cite_data, options), "No citation metadata is recorded.")
})

test_that("invalid citations and options fail explicitly", {
  cache_dir <- tempfile("datamonger-citations-")
  seeded <- seed_conformance_cache(cache_dir)
  index <- seeded$index
  index$schema_version <- 2L
  index$datasets[[1]]$schema_version <- 2L
  for (record in list(
    list(citation = ""), list(citation = "Text", role = "other"),
    list(citation = "Text", recommended = 1L),
    list(citation = "Text", note = NULL), list(citation = "Text", extra = TRUE)
  )) {
    index$datasets[[1]]$provenance$citations <- list(record)
    selector <- reseal_index(index, cache_dir)
    expect_error(cite_data("conformance:mixed_csv", registry = selector,
      cache_dir = cache_dir, offline = TRUE), class = "datamonger_unsupported_registry")
  }
  expect_error(cite_data("conformance:mixed_csv", format = "bibtex"), "format")
  expect_error(cite_data("conformance:mixed_csv", include_all = NA), "include_all")
})
