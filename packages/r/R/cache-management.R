.cache_files <- function(cache_dir, namespace) {
  directory <- file.path(cache_dir, namespace, "sha256")
  if (!dir.exists(directory)) {
    return(character())
  }
  paths <- list.files(directory, full.names = TRUE, all.files = FALSE)
  paths <- paths[
    grepl(.sha256_pattern, basename(paths), perl = TRUE) &
      !is.na(file.info(paths)$isdir) &
      !file.info(paths)$isdir
  ]
  sort(paths)
}

.registry_references <- function(contents) {
  parsed <- tryCatch(
    .parse_json_raw(contents, "cached registry"),
    error = function(error) NULL
  )
  if (is.null(parsed) || !.is_object(parsed) || !identical(parsed$schema_version, 1L)) {
    return(list(release = NULL, references = list()))
  }
  references <- list()
  datasets <- parsed$datasets
  if (is.list(datasets) && is.null(names(datasets))) {
    for (dataset in datasets) {
      if (!.is_object(dataset) || !is.list(dataset$artifacts)) next
      id <- paste0(dataset$source, ":", dataset$name, "@", dataset$version)
      for (artifact in dataset$artifacts) {
        digest <- artifact$sha256
        if (.is_scalar_character(digest) && grepl(.sha256_pattern, digest)) {
          references[[digest]] <- unique(c(references[[digest]], id))
        }
      }
    }
  }
  list(release = parsed$release, references = references)
}

.merge_references <- function(target, source) {
  for (digest in names(source)) {
    target[[digest]] <- sort(unique(c(target[[digest]], source[[digest]])))
  }
  target
}

.inspect_cache_entry <- function(cache_dir, namespace, path) {
  digest <- basename(path)
  lease <- .acquire_lock(
    .lease_path(cache_dir, namespace, digest),
    exclusive = FALSE
  )
  on.exit(.release_lock(lease), add = TRUE)
  if (!file.exists(path)) return(NULL)
  information <- file.info(path)
  contents <- if (identical(namespace, "registries")) .read_raw(path) else NULL
  actual <- .sha256_file(path)
  structure(
    list(
      kind = if (identical(namespace, "registries")) "registry" else "artifact",
      sha256 = digest,
      size = as.numeric(information$size),
      modified_at = information$mtime,
      path = path,
      valid = identical(actual, digest),
      datasets = character(),
      registry_release = NULL,
      contents = contents
    ),
    class = "datamonger_cache_entry"
  )
}

#' Inspect the private R cache
#'
#' This operation does not access the network. It rehashes each object and
#' associates artifacts with dataset versions referenced by bundled and cached
#' registry indexes.
#'
#' @param cache_dir Explicit cache directory, or `NULL` for the consent policy.
#' @return A `datamonger_cache_info` record.
#' @export
cache_info <- function(cache_dir = NULL) {
  cache_dir <- .selected_cache_dir(cache_dir)
  references <- .registry_references(.bundled_registry_bytes())$references
  entries <- list()
  for (namespace in .cache_namespaces) {
    for (path in .cache_files(cache_dir, namespace)) {
      entry <- .inspect_cache_entry(cache_dir, namespace, path)
      if (is.null(entry)) next
      if (identical(entry$kind, "registry") && entry$valid) {
        metadata <- .registry_references(entry$contents)
        entry$registry_release <- metadata$release
        references <- .merge_references(references, metadata$references)
      }
      entry$contents <- NULL
      entries[[length(entries) + 1L]] <- entry
    }
  }
  for (index in seq_along(entries)) {
    if (identical(entries[[index]]$kind, "artifact")) {
      entries[[index]]$datasets <- references[[entries[[index]]$sha256]] %||% character()
    }
  }
  if (length(entries)) {
    order <- order(
      vapply(entries, `[[`, character(1), "kind"),
      vapply(entries, `[[`, character(1), "sha256")
    )
    entries <- entries[order]
  }
  structure(
    list(
      location = cache_dir,
      total_size = sum(vapply(entries, `[[`, numeric(1), "size")),
      entries = entries
    ),
    class = "datamonger_cache_info"
  )
}

.cache_entry_selected <- function(entry, dataset, cutoff) {
  dataset_match <- is.null(dataset) ||
    (identical(entry$kind, "artifact") && dataset %in% entry$datasets)
  age_match <- is.null(cutoff) || entry$modified_at <= cutoff
  dataset_match && age_match
}

#' Manually remove objects from the private R cache
#'
#' Active objects are skipped. With no filters, all registry indexes and
#' artifacts are selected. When both filters are supplied, they intersect.
#'
#' @param dataset Canonical `source:name@version` identifier, or `NULL`.
#' @param older_than A nonnegative `difftime` or number of seconds, or `NULL`.
#' @param cache_dir Explicit cache directory, or `NULL` for the consent policy.
#' @return A `datamonger_cache_clean_result` containing removed and skipped
#'   entries and `bytes_removed`.
#' @export
cache_clean <- function(dataset = NULL, older_than = NULL, cache_dir = NULL) {
  if (!is.null(dataset) &&
      (!.is_scalar_character(dataset) ||
        !grepl(paste0("^", .dataset_id_pattern, "$"), dataset, perl = TRUE))) {
    stop("dataset must be a canonical source:name@version identifier", call. = FALSE)
  }
  if (!is.null(older_than)) {
    seconds <- as.numeric(older_than, units = "secs")
    if (length(seconds) != 1L || is.na(seconds) || !is.finite(seconds) || seconds < 0) {
      stop("older_than must be a nonnegative duration", call. = FALSE)
    }
  } else {
    seconds <- NULL
  }
  info <- cache_info(cache_dir)
  cutoff <- if (is.null(seconds)) NULL else Sys.time() - seconds
  removed <- list()
  skipped <- list()

  for (entry in info$entries) {
    if (!.cache_entry_selected(entry, dataset, cutoff)) next
    namespace <- if (identical(entry$kind, "registry")) "registries" else "objects"
    lease <- .acquire_lock(
      .lease_path(info$location, namespace, entry$sha256),
      exclusive = TRUE,
      timeout = 0
    )
    if (is.null(lease)) {
      skipped[[length(skipped) + 1L]] <- entry
      next
    }
    if (file.exists(entry$path)) {
      current <- file.info(entry$path)
      current_entry <- entry
      current_entry$size <- as.numeric(current$size)
      current_entry$modified_at <- current$mtime
      if (.cache_entry_selected(current_entry, dataset, cutoff)) {
        if (unlink(entry$path) != 0L) {
          .release_lock(lease)
          .abort_category("cache", paste0("cannot remove cache object ", entry$path))
        }
        removed[[length(removed) + 1L]] <- current_entry
      }
    }
    .release_lock(lease)
  }
  structure(
    list(
      location = info$location,
      removed = removed,
      skipped = skipped,
      bytes_removed = sum(vapply(removed, `[[`, numeric(1), "size"))
    ),
    class = "datamonger_cache_clean_result"
  )
}
