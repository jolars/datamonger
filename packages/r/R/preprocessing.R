.preprocessing_metadata <- function(dataset) {
  if (!("preprocessing" %in% names(dataset))) return(NULL)
  fail <- function(message) .abort_category("unsupported-registry", message)
  nonempty <- function(value, field) {
    text <- .require_string(value, field)
    if (!nzchar(text)) fail(paste0(field, " must not be empty"))
    text
  }
  if (!(dataset$schema_version %in% c(3L, 4L))) {
    fail("preprocessing requires manifest schema 3 or 4")
  }
  metadata <- .require_object(dataset$preprocessing, "preprocessing")
  .require_exact_fields(metadata, c("upstream", "datamonger"), "preprocessing",
    "datamonger_unsupported_registry")
  for (stage in metadata) {
    .require_object(stage, "preprocessing stage")
    if (length(setdiff(names(stage), c("status", "steps", "evidence", "notes")))) {
      fail("unknown preprocessing stage field")
    }
    status <- nonempty(stage$status, "preprocessing status")
    if (!(status %in% c("unknown", "none", "documented"))) {
      fail("unsupported preprocessing status")
    }
    if ("notes" %in% names(stage)) nonempty(stage$notes, "preprocessing notes")
    if (status != "unknown" && !("evidence" %in% names(stage))) {
      fail("known preprocessing requires evidence")
    }
    if ("evidence" %in% names(stage)) {
      evidence <- .require_array(stage$evidence, "preprocessing evidence")
      if (!length(evidence)) fail("preprocessing evidence must not be empty")
      for (reference in evidence) nonempty(reference, "preprocessing evidence reference")
    }
    if (status != "documented") {
      if ("steps" %in% names(stage)) fail("only documented processing has steps")
      next
    }
    steps <- .require_array(stage$steps, "preprocessing steps")
    if (!length(steps)) fail("documented preprocessing requires steps")
    for (step in steps) {
      .require_object(step, "preprocessing step")
      if (length(setdiff(names(step), c("kind", "description", "parameters")))) {
        fail("unknown preprocessing step field")
      }
      kind <- nonempty(step$kind, "preprocessing kind")
      if (!grepl(.identifier_pattern, kind, perl = TRUE)) {
        fail("invalid preprocessing kind")
      }
      nonempty(step$description, "preprocessing description")
      if ("parameters" %in% names(step)) {
        parameters <- .require_object(step$parameters, "preprocessing parameters")
        for (key in names(parameters)) {
          nonempty(key, "preprocessing parameter name")
          nonempty(parameters[[key]], "preprocessing parameter value")
        }
      }
    }
  }
  metadata
}
