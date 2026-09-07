test_that("persistent cache use requires explicit consent", {
  old <- options(datamonger.cache_consent = NULL)
  on.exit(options(old), add = TRUE)

  temporary <- datamonger_cache_dir(.interactive = FALSE)
  expect_true(startsWith(temporary, tempdir()))

  options(datamonger.cache_consent = FALSE)
  expect_identical(datamonger_cache_dir(.interactive = FALSE), temporary)

  options(datamonger.cache_consent = TRUE)
  expected <- file.path(tools::R_user_dir("datamonger", "cache"), "r")
  expect_identical(datamonger_cache_dir(.interactive = FALSE), expected)
})

test_that("interactive cache choice is remembered for the session", {
  old <- options(datamonger.cache_consent = NULL)
  on.exit(options(old), add = TRUE)
  asked <- 0L
  ask <- function(...) {
    asked <<- asked + 1L
    TRUE
  }

  first <- datamonger_cache_dir(.interactive = TRUE, .ask = ask)
  second <- datamonger_cache_dir(.interactive = TRUE, .ask = ask)

  expect_identical(asked, 1L)
  expect_identical(
    first,
    file.path(tools::R_user_dir("datamonger", "cache"), "r")
  )
  expect_identical(second, first)
})

test_that("choosing a cache path does not create it", {
  explicit <- file.path(tempdir(), paste0("datamonger-", Sys.getpid()), "cache")
  unlink(dirname(explicit), recursive = TRUE)

  expect_identical(datamonger_cache_dir(explicit), explicit)
  expect_false(dir.exists(explicit))
})
