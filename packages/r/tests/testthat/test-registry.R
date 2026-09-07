test_that("registry selectors validate their strong identity", {
  selected <- registry_selector(
    release = "candidate-0002",
    index_sha256 = paste(rep("a", 64), collapse = ""),
    index_url = "https://example.com/index.json"
  )
  expect_s3_class(selected, "datamonger_registry")
  expect_identical(selected$schema_version, 1L)

  expect_error(
    registry_selector("candidate", "ABC", "https://example.com/index.json"),
    class = "datamonger_registry_integrity"
  )
  expect_error(
    registry_selector("candidate", paste(rep("a", 64), collapse = ""), "file:///tmp/index"),
    class = "datamonger_registry"
  )
  expect_error(
    registry_selector(
      "candidate",
      paste(rep("a", 64), collapse = ""),
      "https://example.com bad"
    ),
    class = "datamonger_registry"
  )
})

test_that("session and nearest-project selectors have defined precedence", {
  old <- active_registry(project_dir = tempdir())
  on.exit(set_registry(NULL), add = TRUE)
  selected <- registry_selector(
    "session-1",
    paste(rep("b", 64), collapse = ""),
    "https://example.com/index.json"
  )

  set_registry(selected)
  expect_identical(active_registry(project_dir = tempdir()), selected)
  set_registry(NULL)
  expect_identical(active_registry(project_dir = tempdir()), old)
})

test_that("the nearest project selector is used after the session setting", {
  root <- tempfile("datamonger-project-")
  child <- file.path(root, "analysis", "notebooks")
  dir.create(child, recursive = TRUE)
  selector_dir <- file.path(root, "analysis", ".datamonger")
  dir.create(selector_dir)
  digest <- paste(rep("c", 64), collapse = "")
  jsonlite::write_json(
    list(
      schema_version = 1L,
      release = "project-1",
      index_sha256 = digest,
      index_url = "https://example.com/index.json"
    ),
    file.path(selector_dir, "selector.json"),
    auto_unbox = TRUE
  )

  selected <- active_registry(project_dir = child)

  expect_identical(selected$release, "project-1")
  expect_identical(selected$index_sha256, digest)
})

test_that("the bundled registry is a verified offline trust root", {
  listed <- list_data(cache_dir = tempfile("datamonger-cache-"), offline = TRUE)

  expect_setequal(
    vapply(listed, `[[`, character(1), "dataset_id"),
    c("libsvm:heart_scale@1", "uci:iris@1")
  )
})
