.error_classes <- c(
  "unknown-dataset" = "datamonger_unknown_dataset",
  "unsupported-registry" = "datamonger_unsupported_registry",
  "unsupported-decoder" = "datamonger_unsupported_decoder",
  "artifact-unavailable" = "datamonger_artifact_unavailable",
  "artifact-offline" = "datamonger_artifact_offline",
  "retrieval-exhausted" = "datamonger_retrieval_exhausted",
  "artifact-integrity" = "datamonger_artifact_integrity",
  "decoded-integrity" = "datamonger_decoded_integrity",
  "cache" = "datamonger_cache",
  "decode" = "datamonger_decode"
)

.condition_class <- function(category) {
  class <- unname(.error_classes[[category]])
  if (is.null(class)) {
    stop("unknown Datamonger error category", call. = FALSE)
  }
  class
}

.condition_parents <- function(class) {
  switch(
    class,
    datamonger_registry_integrity = "datamonger_registry",
    datamonger_registry_release = "datamonger_registry",
    datamonger_registry_retrieval = "datamonger_registry",
    datamonger_registry_offline = c(
      "datamonger_registry_retrieval",
      "datamonger_registry"
    ),
    datamonger_unsupported_registry = "datamonger_registry",
    datamonger_artifact_selection = "datamonger_retrieval",
    datamonger_artifact_unavailable = "datamonger_retrieval",
    datamonger_artifact_offline = "datamonger_retrieval",
    datamonger_retrieval_exhausted = "datamonger_retrieval",
    datamonger_artifact_integrity = "datamonger_retrieval",
    character()
  )
}

.dm_abort <- function(class, message, ..., call = NULL) {
  condition <- c(
    list(message = message, call = call),
    list(...)
  )
  class(condition) <- unique(c(
    class,
    .condition_parents(class),
    "datamonger_error",
    "error",
    "condition"
  ))
  stop(condition)
}

.abort_category <- function(category, message, ...) {
  .dm_abort(.condition_class(category), message, category = category, ...)
}
