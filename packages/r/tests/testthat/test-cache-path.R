test_that("the platform cache is the default", {
  expected <- file.path(tools::R_user_dir("datamonger", "cache"), "r")
  expect_identical(datamonger_cache_dir(), expected)
})

test_that("choosing a cache path does not create it", {
  explicit <- file.path(tempdir(), paste0("datamonger-", Sys.getpid()), "cache")
  unlink(dirname(explicit), recursive = TRUE)

  expect_identical(datamonger_cache_dir(explicit), explicit)
  expect_false(dir.exists(explicit))
})
