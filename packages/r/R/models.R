.new_registry <- function(release, index_sha256, index_url, schema_version = 1L) {
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

print.datamonger_registry <- function(x, ...) {
  cat(
    "<datamonger_registry>", x$release, "\n",
    "  index_sha256: ", x$index_sha256, "\n",
    "  index_url: ", x$index_url, "\n",
    sep = ""
  )
  invisible(x)
}

print.datamonger_fetch_info <- function(x, ...) {
  cat(
    "<datamonger_fetch_info>", x$dataset_id, "\n",
    "  registry: ", x$registry_release, "\n",
    "  verification: ", x$verification, "\n",
    sep = ""
  )
  invisible(x)
}

print.datamonger_data_info <- function(x, ...) {
  cat(
    "<datamonger_data_info>", x$dataset_id, "\n",
    "  ", x$title, "\n",
    "  registry: ", x$registry_release, "\n",
    sep = ""
  )
  invisible(x)
}

print.datamonger_cache_info <- function(x, ...) {
  cat(
    "<datamonger_cache_info>\n",
    "  location: ", x$location, "\n",
    "  entries: ", length(x$entries), "\n",
    "  total_size: ", x$total_size, " bytes\n",
    sep = ""
  )
  invisible(x)
}
