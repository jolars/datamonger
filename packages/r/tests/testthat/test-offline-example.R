test_that("installed offline example inputs match the shared corpus and registry", {
  example <- system.file("extdata", "offline-conformance", package = "datamonger",
                         mustWork = TRUE)
  for (path in list.files(fixture_path("conformance"), recursive = TRUE)) {
    expect_identical(
      readBin(file.path(example, "conformance", path), "raw", n = 1e6),
      readBin(fixture_path("conformance", path), "raw", n = 1e6),
      info = path
    )
  }
  for (path in c("selector.json", "index.json")) {
    expect_identical(
      readBin(file.path(example, "registry", path), "raw", n = 1e6),
      readBin(fixture_path("registry", path), "raw", n = 1e6),
      info = path
    )
  }
})

test_that("the offline article executes retrieval, decoding, tables, and a figure", {
  root <- getNamespaceInfo(asNamespace("datamonger"), "path")
  article <- file.path(root, "vignettes", "offline-conformance.Rmd")
  if (!file.exists(article)) {
    article <- system.file("doc", "offline-conformance.Rmd", package = "datamonger",
                           mustWork = TRUE)
  }
  stage <- tempfile("datamonger-offline-article-")
  dir.create(stage)
  previous <- setwd(stage)
  on.exit({
    setwd(previous)
    unlink(stage, recursive = TRUE)
  }, add = TRUE)
  stopifnot(file.copy(article, "offline-conformance.Rmd"))
  env <- new.env(parent = globalenv())
  testthat::with_mocked_bindings(
    knitr::knit("offline-conformance.Rmd", "article.md", envir = env, quiet = TRUE),
    .download_url_to_file = function(...) stop("Offline examples must not use the network"),
    .package = "datamonger"
  )
  markdown <- paste(readLines("article.md", warn = FALSE), collapse = "\n")
  expect_match(markdown, "The decoded result has 5 rows and 4 columns", fixed = TRUE)
  expect_match(markdown, "quoted, value", fixed = TRUE)
  expect_match(markdown, env$case$expected_sha256, fixed = TRUE)
  expect_match(markdown, "Four observed measurements", fixed = TRUE)
  expect_true(length(list.files("figure", pattern = "\\.png$")) == 1L)
  expect_identical(env$result$info$verification, "decoded")
  expect_false(dir.exists(env$cache_dir))
})
