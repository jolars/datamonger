.new_registry <- function(
  release,
  index_sha256,
  index_url,
  schema_version = 1L
) {
  structure(
    list(
      release = release,
      index_sha256 = index_sha256,
      index_url = index_url,
      schema_version = schema_version
    ),
    class = "datamonger_registry"
  )
}

#' Display Registry, Fetch, Dataset, and Cache Metadata
#'
#' Print compact summaries of Datamonger metadata objects. The methods read the
#' object's fields without retrieving data or inspecting the cache again.
#'
#' @param x A Datamonger registry selector, fetch metadata record, dataset
#'   metadata record, or cache inventory matching the method's class.
#' @param ... Additional arguments, ignored by these print methods.
#' @details
#' Registry selectors returned by `registry_selector()`, `resolve_registry()`,
#' or `active_registry()` display the release, index SHA-256, and index URL.
#'
#' The `info` member returned by `fetch_data(return_info = TRUE)` displays the
#' resolved dataset identifier, registry release, and completed verification
#' level.
#'
#' Dataset records returned by `data_info()` or in the list returned by
#' `list_data()` display the resolved dataset identifier, title, and registry
#' release.
#'
#' Cache inventories returned by `cache_info()` display the cache location,
#' entry count, and total size in bytes. These summaries describe the inventory
#' at the time it was collected.
#'
#' @returns Each print method returns `x` invisibly.
#'
#' @seealso [registry_selector()], [fetch_data()], [data_info()], [cache_info()]
#'
#' @name datamonger_metadata
#' @aliases datamonger_registry
#' @aliases datamonger_fetch_info
#' @aliases datamonger_data_info
#' @aliases datamonger_cache_info
#' @rdname metadata-print
#' @exportS3Method print datamonger_registry
print.datamonger_registry <- function(x, ...) {
  cat(
    "<datamonger_registry>",
    x$release,
    "\n",
    "  index_sha256: ",
    x$index_sha256,
    "\n",
    "  index_url: ",
    x$index_url,
    "\n",
    sep = ""
  )
  invisible(x)
}

#' @rdname metadata-print
#' @exportS3Method print datamonger_fetch_info
print.datamonger_fetch_info <- function(x, ...) {
  cat(
    "<datamonger_fetch_info>",
    x$dataset_id,
    "\n",
    "  registry: ",
    x$registry_release,
    "\n",
    "  verification: ",
    x$verification,
    "\n",
    sep = ""
  )
  invisible(x)
}

#' @rdname metadata-print
#' @exportS3Method print datamonger_data_info
print.datamonger_data_info <- function(x, ...) {
  cat(
    "<datamonger_data_info>",
    x$dataset_id,
    "\n",
    "  ",
    x$title,
    "\n",
    "  registry: ",
    x$registry_release,
    "\n",
    sep = ""
  )
  invisible(x)
}

#' @rdname metadata-print
#' @exportS3Method print datamonger_cache_info
print.datamonger_cache_info <- function(x, ...) {
  cat(
    "<datamonger_cache_info>\n",
    "  location: ",
    x$location,
    "\n",
    "  entries: ",
    length(x$entries),
    "\n",
    "  total_size: ",
    x$total_size,
    " bytes\n",
    sep = ""
  )
  invisible(x)
}
