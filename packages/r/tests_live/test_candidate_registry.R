pkgload::load_all(".", quiet = TRUE)

selector_document <- jsonlite::fromJSON(
  "../../registry/releases/candidate-0002/selector.json",
  simplifyVector = FALSE
)
index <- jsonlite::fromJSON(
  "../../registry/releases/candidate-0002/index.json",
  simplifyVector = FALSE
)
selected <- do.call(registry_selector, selector_document)
cache_dir <- file.path(tempdir(), "datamonger-candidate-0002")

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
