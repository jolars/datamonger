fixture_path <- function(...) {
  testthat::test_path("fixtures", ...)
}

read_fixture_json <- function(...) {
  jsonlite::fromJSON(
    fixture_path(...),
    simplifyVector = FALSE,
    bigint_as_char = TRUE
  )
}

dm_internal <- function(name) {
  getFromNamespace(name, "datamonger")
}

write_bytes <- function(contents) {
  path <- tempfile()
  writeBin(contents, path)
  path
}

write_text <- function(text) {
  write_bytes(charToRaw(enc2utf8(text)))
}

conformance_recipe <- function(index) {
  read_fixture_json("conformance", "cases.json")$cases[[index]]$recipe
}

compress_fixture <- function(path, compression) {
  destination <- tempfile()
  connection <- switch(
    compression,
    gzip = gzfile(destination, "wb"),
    bzip2 = bzfile(destination, "wb")
  )
  writeBin(readBin(path, "raw", n = file.info(path)$size), connection)
  close(connection)
  destination
}

seed_conformance_cache <- function(cache_dir) {
  selector <- read_fixture_json("registry", "selector.json")
  index <- read_fixture_json("registry", "index.json")
  registry_dir <- file.path(cache_dir, "registries", "sha256")
  object_dir <- file.path(cache_dir, "objects", "sha256")
  dir.create(registry_dir, recursive = TRUE)
  dir.create(object_dir, recursive = TRUE)
  file.copy(
    fixture_path("registry", "index.json"),
    file.path(registry_dir, selector$index_sha256)
  )

  artifacts <- list.files(
    fixture_path("conformance", "artifacts"),
    full.names = TRUE
  )
  for (path in artifacts) {
    raw <- readBin(path, "raw", n = file.info(path)$size)
    digest <- digest::digest(raw, algo = "sha256", serialize = FALSE)
    file.copy(path, file.path(object_dir, digest))
  }
  list(
    selector = do.call(registry_selector, selector),
    index = index
  )
}
