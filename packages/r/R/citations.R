.citation_metadata <- function(dataset) {
  provenance <- .require_object(dataset$provenance %||% list(), "provenance")
  fields <- names(provenance)
  fail <- function(message) .abort_category("unsupported-registry", message)
  nonempty <- function(value, field) {
    value <- .require_string(value, field)
    if (!nzchar(value)) fail(paste0(field, " must not be empty"))
    value
  }
  if (all(c("citation", "citations") %in% fields)) {
    fail("provenance cannot contain citation and citations")
  }
  if (
    identical(dataset$schema_version, 1L) &&
      any(c("citations", "citation_instructions") %in% fields)
  ) {
    fail("multiple citations require manifest schema 2")
  }
  instructions <- if ("citation_instructions" %in% fields) {
    nonempty(provenance$citation_instructions, "citation instructions")
  } else {
    NULL
  }
  if ("citation" %in% fields) {
    records <- list(list(citation = nonempty(provenance$citation, "citation")))
  } else {
    records <- if ("citations" %in% fields) {
      .require_array(provenance$citations, "citations")
    } else {
      list()
    }
    for (record in records) {
      .require_object(record, "citation record")
      if (
        length(setdiff(
          names(record),
          c("citation", "role", "note", "recommended")
        ))
      ) {
        fail("unknown citation record field")
      }
      nonempty(record$citation, "citation")
      if (
        "role" %in% names(record) &&
          !(nonempty(record$role, "citation role") %in%
            c("dataset", "paper", "collection"))
      ) {
        fail("unsupported citation role")
      }
      if ("note" %in% names(record)) {
        nonempty(record$note, "citation note")
      }
      if (
        "recommended" %in% names(record) &&
          !.is_scalar_logical(record$recommended)
      ) {
        fail("citation recommended must be a boolean")
      }
    }
  }
  list(citations = records, citation_instructions = instructions)
}

#' Get curated citations without retrieving dataset artifacts
#'
#' @inheritParams fetch_artifact
#' @param include_all Return every reference, including those not recommended.
#' @param format Either `"text"` or `"records"`.
#' @return
#' A character string, or a list of citation records. By default, select
#' references marked as recommended by upstream. If no recommendation flags are
#' recorded, return all references and explain the unknown recommendation in
#' text output. Records preserve optional roles, notes, and recommendation
#' flags. Full records and upstream instructions are available in `data_info()`
#' and fetch metadata with `return_info = TRUE`.
#' @export
cite_data <- function(
  name,
  source = NULL,
  version = NULL,
  registry = NULL,
  cache_dir = NULL,
  offline = FALSE,
  include_all = FALSE,
  format = "text"
) {
  if (!.is_scalar_logical(include_all)) {
    stop("include_all must be TRUE or FALSE", call. = FALSE)
  }
  if (
    !is.character(format) ||
      length(format) != 1L ||
      is.na(format) ||
      !(format %in% c("text", "records"))
  ) {
    stop("format must be 'text' or 'records'", call. = FALSE)
  }
  info <- data_info(name, source, version, registry, cache_dir, offline)
  records <- info$citations
  known <- any(vapply(
    records,
    function(x) "recommended" %in% names(x),
    logical(1)
  ))
  selected <- if (include_all || !known) {
    records
  } else {
    Filter(function(x) isTRUE(x$recommended), records)
  }
  if (identical(format, "records")) {
    return(selected)
  }
  paragraphs <- info$citation_instructions %||% character()
  if (!length(records)) {
    paragraphs <- c(paragraphs, "No citation metadata is recorded.")
  } else if (!known) {
    paragraphs <- c(
      paragraphs,
      "No upstream citation recommendation is recorded."
    )
  } else if (!length(selected)) {
    paragraphs <- c(paragraphs, "No references are marked as recommended.")
  }
  for (record in selected) {
    role <- if (is.null(record$role)) "" else paste0("[", record$role, "] ")
    text <- paste0(role, record$citation)
    if (!is.null(record$note)) {
      text <- paste0(text, "\n", record$note)
    }
    paragraphs <- c(paragraphs, text)
  }
  paste(paragraphs, collapse = "\n\n")
}
