test_that("the introduction renders metadata without downloads", {
  root <- getNamespaceInfo(asNamespace("datamonger"), "path")
  article <- file.path(root, "vignettes", "introduction.Rmd")
  if (!file.exists(article)) {
    article <- system.file("doc", "introduction.Rmd", package = "datamonger",
                           mustWork = TRUE)
  }
  stage <- tempfile("datamonger-introduction-")
  dir.create(stage)
  previous <- setwd(stage)
  on.exit({
    setwd(previous)
    unlink(stage, recursive = TRUE)
  }, add = TRUE)
  stopifnot(file.copy(article, "introduction.Rmd"))
  env <- new.env(parent = globalenv())
  testthat::with_mocked_bindings(
    knitr::knit("introduction.Rmd", "article.md", envir = env, quiet = TRUE),
    .download_url_to_file = function(...) stop("Vignettes must not use the network"),
    .package = "datamonger"
  )
  expect_true(length(env$available) > 0L)
  expect_identical(env$info$dataset_id, "uci:iris@1")
  expect_false(exists("flowers", envir = env, inherits = FALSE))
  expect_setequal(list.files(stage), c("introduction.Rmd", "article.md"))
})
