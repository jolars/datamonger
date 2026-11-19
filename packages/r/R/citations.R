.citation_metadata <- function(dataset) {
  provenance <- .require_object(dataset$provenance %||% list(), "provenance")
  fields <- names(provenance)
  fail <- function(message) {
    .abort_category("unsupported-registry", message)
  }
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

#' Get Curated Dataset Citations
#'
#' Retrieve curated citations from the selected registry without downloading
#' artifacts or looking up bibliographic identifiers. Multiple references can be
#' recommended together. Optional roles describe a dataset, paper, or
#' collection; roles do not imply recommendations.
#'
#' @param name A bare dataset name, `source:name`, or `source:name@version`.
#' @param source Dataset source. Required for bare names; omit for qualified
#'   references.
#' @param version Exact dataset version. Omit when embedded in `name`. An
#'   omitted version selects the registry default.
#' @param registry A strong selector, or `NULL` for the active selector.
#' @param cache_dir An explicit cache directory, or `NULL` for the platform
#'   default.
#' @param offline Whether to use only bundled or verified cached registry bytes.
#' @param include_all Whether to include every reference regardless of
#'   recommendation.
#' @param format Either `"text"` or `"records"`.
#' @details
#' By default, return references explicitly marked as recommended by upstream.
#' If no reference carries a recommendation flag, return all references and
#' explain the unknown recommendation in text output. If flags exist but none is
#' true, return an empty selection. Missing citation metadata produces an
#' explicit text message or an empty list. The legacy single citation remains
#' supported.
#'
#' All references and upstream instructions are also available as `citations`
#' and `citation_instructions` in `data_info()` and fetch metadata from
#' `fetch_data(return_info = TRUE)`. An absent recommendation flag means
#' unknown, whereas `FALSE` records that the reference is not recommended.
#'
#' @returns
#' A character string with role labels, notes, and upstream instructions, or a
#' list of citation records with optional `role`, `note`, and `recommended`
#' fields preserved.
#'
#' @seealso [data_info()], [fetch_data()]
#'
#' @examples
#' cat(cite_data(
#'   "uci:iris",
#'   registry = active_registry(tempdir()),
#'   cache_dir = tempfile("datamonger-cache-"),
#'   offline = TRUE
#' ))
#'
#' @rdname cite-data
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
