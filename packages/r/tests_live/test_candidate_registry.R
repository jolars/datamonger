pkgload::load_all(".", quiet = TRUE)

args <- commandArgs(trailingOnly = TRUE)
release <- if (length(args)) args[[1L]] else "candidate-0002"
release_root <- file.path("../../registry/releases", release)
selector_document <- jsonlite::fromJSON(
  file.path(release_root, "selector.json"),
  simplifyVector = FALSE
)
index <- jsonlite::fromJSON(
  file.path(release_root, "index.json"),
  simplifyVector = FALSE
)
selected <- do.call(registry_selector, selector_document)
cache_dir <- tempfile(paste0("datamonger-", release, "-"))

for (dataset in index$datasets) {
  result <- fetch_data(
    dataset$name,
    source = dataset$source,
    version = dataset$version,
    registry = selected,
    cache_dir = cache_dir,
    return_info = TRUE
  )
  records <- dataset$representation$expect$verification
  expected <- tail(records, 1L)[[1]]$digest
  stopifnot(identical(result$info$canonical_digest, expected))
  message(result$info$dataset_id, " ", result$info$canonical_digest)
}
