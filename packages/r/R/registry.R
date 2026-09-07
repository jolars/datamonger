.bundled_registry <- .new_registry(
  release = "proof-0001",
  index_sha256 = "98cdbc7c8c795dcd021775de4c955c2442e6e1f2d7911e4c53b72327d90f6578",
  index_url = paste0(
    "https://github.com/jolars/datamonger/releases/download/",
    "registry-proof-0001/index.json"
  )
)
.default_catalog_url <- paste0(
  "https://raw.githubusercontent.com/jolars/datamonger/",
  "main/registry/catalog.json"
)
.session_state <- new.env(parent = emptyenv())
.session_state$registry <- NULL

.validate_registry <- function(registry) {
  if (!inherits(registry, "datamonger_registry")) {
    .dm_abort("datamonger_registry", "registry must be a registry selector")
  }
  if (!identical(registry$schema_version, 1L)) {
    .abort_category(
      "unsupported-registry",
      paste0("unsupported registry selector schema ", registry$schema_version)
    )
  }
  if (!.is_scalar_character(registry$release) ||
      !grepl(.release_pattern, registry$release, perl = TRUE)) {
    .dm_abort("datamonger_registry", "registry release identifier is invalid")
  }
  if (!.is_scalar_character(registry$index_sha256) ||
      !grepl(.sha256_pattern, registry$index_sha256, perl = TRUE)) {
    .dm_abort(
      "datamonger_registry_integrity",
      "registry SHA-256 must contain 64 lowercase hexadecimal digits"
    )
  }
  if (!.is_http_url(registry$index_url)) {
    .dm_abort("datamonger_registry", "registry index URL must be HTTP or HTTPS")
  }
  invisible(registry)
}

#' Construct a strong registry selector
#'
#' The release and SHA-256 digest form the strong identity. The URL is only a
#' retrieval location.
#'
#' @param release Registry release identifier.
#' @param index_sha256 Lowercase SHA-256 of the exact index bytes.
#' @param index_url Absolute HTTP or HTTPS index URL.
#' @param schema_version Selector schema version. Revision 1 requires `1`.
#' @return A `datamonger_registry` selector.
#' @export
registry_selector <- function(
    release,
    index_sha256,
    index_url,
    schema_version = 1L) {
  selected <- .new_registry(
    release = release,
    index_sha256 = index_sha256,
    index_url = index_url,
    schema_version = schema_version
  )
  .validate_registry(selected)
  selected
}

.selector_from_list <- function(value, description = "registry selector") {
  .require_exact_fields(
    value,
    c("schema_version", "release", "index_sha256", "index_url"),
    description,
    "datamonger_registry"
  )
  if (!.is_scalar_character(value$release) ||
      !.is_scalar_character(value$index_sha256) ||
      !.is_scalar_character(value$index_url)) {
    .dm_abort(
      "datamonger_registry",
      paste0(description, " string fields must be strings")
    )
  }
  registry_selector(
    release = value$release,
    index_sha256 = value$index_sha256,
    index_url = value$index_url,
    schema_version = value$schema_version
  )
}

#' Resolve a release through the mutable HTTPS catalog
#'
#' This is a TLS-trusted convenience lookup, not a cryptographic pin. Record
#' and reuse the returned strong selector when reproducibility matters.
#'
#' @param release Bare release identifier.
#' @param catalog_url Absolute HTTPS release-catalog URL.
#' @return A `datamonger_registry` selector.
#' @export
resolve_registry <- function(release, catalog_url = NULL) {
  if (!.is_scalar_character(release) ||
      !grepl(.release_pattern, release, perl = TRUE)) {
    .dm_abort("datamonger_registry", "registry release identifier is invalid")
  }
  if (is.null(catalog_url)) {
    catalog_url <- .default_catalog_url
  }
  if (!.is_http_url(catalog_url, https_only = TRUE)) {
    .dm_abort("datamonger_registry", "registry catalog URL must be HTTPS")
  }
  contents <- .retrieve_url_raw(catalog_url, require_https = TRUE)
  catalog <- .parse_json_raw(contents, "registry catalog")
  .require_exact_fields(
    catalog,
    c("schema_version", "releases"),
    "registry catalog",
    "datamonger_registry"
  )
  if (!identical(catalog$schema_version, 1L)) {
    .abort_category(
      "unsupported-registry",
      paste0("unsupported registry catalog schema ", catalog$schema_version)
    )
  }
  releases <- .require_array(
    catalog$releases,
    "registry catalog releases",
    "datamonger_registry"
  )
  selectors <- lapply(
    releases,
    .selector_from_list,
    description = "registry catalog selector"
  )
  identifiers <- vapply(selectors, `[[`, character(1), "release")
  if (anyDuplicated(identifiers)) {
    .dm_abort("datamonger_registry", "registry catalog releases must be unique")
  }
  match <- which(identifiers == release)
  if (length(match) != 1L) {
    .dm_abort(
      "datamonger_registry",
      paste0("unknown registry release '", release, "'")
    )
  }
  selectors[[match]]
}

#' Set the session registry selector
#'
#' @param registry A strong selector, or `NULL` to clear the session setting.
#' @return `NULL`, invisibly.
#' @export
set_registry <- function(registry) {
  if (!is.null(registry)) {
    .validate_registry(registry)
  }
  .session_state$registry <- registry
  invisible(NULL)
}

.project_selector_path <- function(start) {
  directory <- normalizePath(start, mustWork = TRUE)
  repeat {
    candidate <- file.path(directory, ".datamonger", "selector.json")
    if (file.exists(candidate)) {
      if (isTRUE(file.info(candidate)$isdir)) {
        .dm_abort(
          "datamonger_registry",
          paste0("project selector ", candidate, " must be a file")
        )
      }
      return(candidate)
    }
    parent <- dirname(directory)
    if (identical(parent, directory)) {
      return(NULL)
    }
    directory <- parent
  }
}

.read_project_registry <- function(path) {
  selector <- .parse_json_raw(
    .read_raw(path, "datamonger_registry"),
    paste0("project selector ", path),
    "datamonger_registry"
  )
  .selector_from_list(selector, paste0("project selector ", path))
}

#' Return the active registry selector
#'
#' Selection precedence is the session setting, the nearest project selector,
#' and the bundled immutable selector.
#'
#' @param project_dir Directory from which to search upward for
#'   `.datamonger/selector.json`.
#' @return A `datamonger_registry` selector.
#' @export
active_registry <- function(project_dir = getwd()) {
  if (!is.null(.session_state$registry)) {
    return(.session_state$registry)
  }
  path <- .project_selector_path(project_dir)
  if (!is.null(path)) {
    return(.read_project_registry(path))
  }
  .bundled_registry
}

.bundled_registry_bytes <- function() {
  path <- system.file("extdata", "index.json", package = "datamonger")
  if (!nzchar(path)) {
    .dm_abort(
      "datamonger_registry_retrieval",
      "cannot locate the bundled registry index"
    )
  }
  .read_raw(path, "datamonger_registry_retrieval")
}

.is_bundled_registry <- function(registry) {
  identical(registry$release, .bundled_registry$release) &&
    identical(registry$index_sha256, .bundled_registry$index_sha256)
}

.load_registry <- function(registry, cache_dir, offline = FALSE) {
  .validate_registry(registry)
  if (.is_bundled_registry(registry)) {
    contents <- .bundled_registry_bytes()
    actual <- .sha256_raw(contents)
    if (!identical(actual, registry$index_sha256)) {
      .dm_abort(
        "datamonger_registry_integrity",
        paste0(
          "bundled registry SHA-256 mismatch: expected ",
          registry$index_sha256,
          ", received ",
          actual
        )
      )
    }
  } else {
    leased <- .retrieve_cached_object(
      cache_dir = cache_dir,
      namespace = "registries",
      digest = registry$index_sha256,
      size = NULL,
      urls = registry$index_url,
      offline = offline,
      integrity_class = "datamonger_registry_integrity",
      offline_class = "datamonger_registry_offline",
      retrieval_class = "datamonger_registry_retrieval"
    )
    on.exit(.release_lock(leased$lease), add = TRUE)
    contents <- .read_raw(leased$path, "datamonger_registry")
  }
  index <- .parse_json_raw(contents, "verified registry index")
  .require_object(index, "registry index")
  if (!identical(index$schema_version, 1L)) {
    .abort_category(
      "unsupported-registry",
      paste0("unsupported registry schema ", index$schema_version)
    )
  }
  if (!identical(index$release, registry$release)) {
    .dm_abort(
      "datamonger_registry_release",
      paste0(
        "selected release '", registry$release,
        "' does not match embedded release '", index$release, "'"
      )
    )
  }
  .require_array(index$datasets, "registry datasets")
  .require_array(index$defaults, "registry defaults")
  index
}

.resolve_dataset <- function(index, source, name, version = NULL) {
  valid <- .is_scalar_character(source) &&
    grepl(.identifier_pattern, source, perl = TRUE) &&
    .is_scalar_character(name) &&
    grepl(.identifier_pattern, name, perl = TRUE) &&
    (is.null(version) || (
      .is_scalar_character(version) &&
        grepl(.version_pattern, version, perl = TRUE)
    ))
  requested <- paste0(source, ":", name, if (!is.null(version)) paste0("@", version))
  if (!valid) {
    .abort_category("unknown-dataset", paste0("invalid or unknown dataset ", requested))
  }

  resolved_version <- version
  if (is.null(resolved_version)) {
    matches <- Filter(
      function(default) {
        .require_object(default, "registry default")
        identical(default$source, source) && identical(default$name, name)
      },
      index$defaults
    )
    if (length(matches) != 1L || !.is_scalar_character(matches[[1]]$version)) {
      .abort_category("unknown-dataset", paste0("unknown dataset ", requested))
    }
    resolved_version <- matches[[1]]$version
  }

  matches <- Filter(
    function(dataset) {
      .require_object(dataset, "registry dataset")
      identical(dataset$source, source) &&
        identical(dataset$name, name) &&
        identical(dataset$version, resolved_version)
    },
    index$datasets
  )
  if (length(matches) != 1L) {
    .abort_category(
      "unknown-dataset",
      paste0("unknown dataset ", source, ":", name, "@", resolved_version)
    )
  }
  dataset <- matches[[1]]
  if (!identical(dataset$schema_version, 1L)) {
    .abort_category(
      "unsupported-registry",
      paste0("unsupported dataset schema ", dataset$schema_version)
    )
  }
  dataset
}
