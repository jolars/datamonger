.selected_registry <- function(registry) {
  if (is.null(registry)) active_registry() else registry
}

.selected_cache_dir <- function(cache_dir) {
  datamonger_cache_dir(cache_dir)
}

.dataset_artifacts <- function(dataset) {
  artifacts <- .require_array(dataset$artifacts, "dataset artifacts")
  lapply(artifacts, .require_object, field = "artifact")
}

.select_artifact <- function(dataset, artifact = NULL) {
  artifacts <- .dataset_artifacts(dataset)
  names <- vapply(
    artifacts,
    function(value) .require_string(value$name, "artifact name"),
    character(1)
  )
  if (is.null(artifact)) {
    if (length(artifacts) == 1L) {
      return(artifacts[[1]])
    }
    .dm_abort(
      "datamonger_artifact_selection",
      paste0("artifact name is required; available artifacts: ", paste(names, collapse = ", "))
    )
  }
  match <- which(names == artifact)
  if (length(match) != 1L) {
    .dm_abort(
      "datamonger_artifact_selection",
      paste0("unknown artifact '", artifact, "'; available artifacts: ", paste(names, collapse = ", "))
    )
  }
  artifacts[[match]]
}

.representation_artifacts <- function(dataset, representation, roles) {
  inputs <- .require_object(representation$inputs, "representation inputs")
  if (!identical(sort(names(inputs)), sort(roles))) {
    .abort_category(
      "unsupported-registry",
      paste0("representation inputs must be exactly: ", paste(roles, collapse = ", "))
    )
  }
  artifacts <- .dataset_artifacts(dataset)
  artifact_names <- vapply(artifacts, `[[`, character(1), "name")
  lapply(roles, function(role) {
    name <- .require_string(inputs[[role]], paste0("representation input ", role))
    match <- which(artifact_names == name)
    if (length(match) != 1L) {
      .abort_category(
        "unsupported-registry",
        paste0("representation input refers to unknown artifact '", name, "'")
      )
    }
    artifacts[[match]]
  })
}

.artifact_locations <- function(artifact) {
  name <- .require_string(artifact$name, "artifact name")
  distribution <- .require_string(artifact$distribution, "artifact distribution")
  if (identical(distribution, "metadata-only")) {
    .abort_category(
      "artifact-unavailable",
      paste0("artifact '", name, "' is metadata-only")
    )
  }
  if (!(distribution %in% c("mirror", "upstream-only"))) {
    .abort_category(
      "unsupported-registry",
      paste0("artifact '", name, "' has unsupported distribution")
    )
  }
  downloads <- .require_array(artifact$downloads, "artifact downloads")
  if (!length(downloads)) {
    .abort_category("unsupported-registry", "artifact has no retrieval locations")
  }
  vapply(downloads, function(download) {
    .require_object(download, "artifact download")
    kind <- .require_string(download$kind, "artifact download kind")
    if (!(kind %in% c("mirror", "upstream"))) {
      .abort_category("unsupported-registry", "unsupported artifact download kind")
    }
    url <- .require_string(download$url, "artifact download URL")
    if (!.is_http_url(url)) {
      .abort_category("unsupported-registry", "artifact download URL is invalid")
    }
    url
  }, character(1))
}

.retrieve_artifact <- function(artifact, cache_dir, offline) {
  urls <- .artifact_locations(artifact)
  digest <- .require_string(artifact$sha256, "artifact SHA-256")
  if (!grepl(.sha256_pattern, digest, perl = TRUE)) {
    .abort_category("unsupported-registry", "artifact SHA-256 is invalid")
  }
  .retrieve_cached_object(
    cache_dir = cache_dir,
    namespace = "objects",
    digest = digest,
    size = .require_integer(artifact$size, "artifact size"),
    urls = urls,
    offline = offline,
    integrity_class = "datamonger_artifact_integrity",
    offline_class = "datamonger_artifact_offline",
    retrieval_class = "datamonger_retrieval_exhausted"
  )
}

#' Retrieve one verified artifact without decoding it
#'
#' @param name Dataset name.
#' @param source Dataset source.
#' @param version Exact dataset version, or `NULL` to resolve the registry
#'   default.
#' @param artifact Artifact name. It may be omitted for a single-artifact
#'   dataset.
#' @param registry Strong registry selector, or `NULL` for the active selector.
#' @param cache_dir Explicit cache directory, or `NULL` for the platform default.
#' @param offline If `TRUE`, use verified cached bytes without network access.
#' @return The path to verified artifact bytes in the R client's private cache.
#' @export
fetch_artifact <- function(
    name,
    source,
    version = NULL,
    artifact = NULL,
    registry = NULL,
    cache_dir = NULL,
    offline = FALSE) {
  cache_dir <- .selected_cache_dir(cache_dir)
  registry <- .selected_registry(registry)
  index <- .load_registry(registry, cache_dir, offline)
  dataset <- .resolve_dataset(index, source, name, version)
  leased <- .retrieve_artifact(.select_artifact(dataset, artifact), cache_dir, offline)
  .release_lock(leased$lease)
  leased$path
}

.data_info <- function(dataset, registry) {
  representation <- .require_object(dataset$representation, "dataset representation")
  expect <- .require_object(representation$expect, "representation expectation")
  structure(
    list(
      dataset_id = paste0(dataset$source, ":", dataset$name, "@", dataset$version),
      source = .require_string(dataset$source, "dataset source"),
      name = .require_string(dataset$name, "dataset name"),
      version = .require_string(dataset$version, "dataset version"),
      registry_release = registry$release,
      registry_index_sha256 = registry$index_sha256,
      title = .require_string(dataset$title, "dataset title"),
      description = .require_string(dataset$description, "dataset description"),
      modality = .require_string(dataset$modality, "dataset modality"),
      provenance = .require_object(dataset$provenance, "dataset provenance"),
      license = .require_object(dataset$license, "dataset license"),
      artifacts = .dataset_artifacts(dataset),
      representation = representation,
      expected_components = .require_array(expect$components, "expected components"),
      verification_records = .require_array(expect$verification, "verification records"),
      related = dataset$related %||% list(),
      tasks = dataset$tasks %||% list()
    ),
    class = "datamonger_data_info"
  )
}

#' Inspect one registered dataset without retrieving artifacts
#'
#' @inheritParams fetch_artifact
#' @return A `datamonger_data_info` record with identity, provenance, license,
#'   representation, task, and verification metadata.
#' @export
data_info <- function(
    name,
    source,
    version = NULL,
    registry = NULL,
    cache_dir = NULL,
    offline = FALSE) {
  cache_dir <- .selected_cache_dir(cache_dir)
  registry <- .selected_registry(registry)
  index <- .load_registry(registry, cache_dir, offline)
  .data_info(.resolve_dataset(index, source, name, version), registry)
}

#' List dataset versions in the selected registry
#'
#' @param registry Strong registry selector, or `NULL` for the active selector.
#' @param cache_dir Explicit cache directory, or `NULL` for the platform default.
#' @param offline If `TRUE`, use a bundled or verified cached registry only.
#' @return A list of `datamonger_data_info` records.
#' @export
list_data <- function(registry = NULL, cache_dir = NULL, offline = FALSE) {
  cache_dir <- .selected_cache_dir(cache_dir)
  registry <- .selected_registry(registry)
  index <- .load_registry(registry, cache_dir, offline)
  lapply(index$datasets, function(dataset) {
    source <- .require_string(dataset$source, "dataset source")
    name <- .require_string(dataset$name, "dataset name")
    version <- .require_string(dataset$version, "dataset version")
    .data_info(.resolve_dataset(index, source, name, version), registry)
  })
}

.component_matches <- function(component, expectation) {
  if (!identical(component$kind, expectation$kind) ||
      !identical(component$name, expectation$name) ||
      !identical(component$logical_type, expectation$type %||% component$logical_type)) {
    return(FALSE)
  }
  if (identical(component$kind, "vector")) {
    return(identical(as.numeric(length(component$values)), as.numeric(expectation$length)))
  }
  identical(as.numeric(component$rows), as.numeric(expectation$rows)) &&
    identical(as.numeric(component$columns), as.numeric(expectation$columns))
}

.validate_components <- function(components, expected) {
  expected <- .require_array(expected, "expected components")
  if (length(components) != length(expected)) {
    .abort_category(
      "decoded-integrity",
      paste0("expected ", length(expected), " components, decoded ", length(components))
    )
  }
  for (index in seq_along(components)) {
    expectation <- .require_object(expected[[index]], "component expectation")
    if (!.component_matches(components[[index]], expectation)) {
      .abort_category(
        "decoded-integrity",
        paste0("decoded component '", components[[index]]$name, "' does not match its expectation")
      )
    }
  }
  invisible(NULL)
}

.verification_record <- function(index, dataset, expect) {
  identity <- list(
    source = dataset$source,
    name = dataset$name,
    version = dataset$version
  )
  errata <- index$errata %||% list()
  .require_array(errata, "registry errata")
  revoked <- list()
  for (erratum in errata) {
    .require_object(erratum, "registry erratum")
    if (.json_equal(erratum$dataset, identity) &&
        identical(erratum$target$kind, "verification")) {
      revoked[[length(revoked) + 1L]] <- erratum$original
    }
  }
  records <- .require_array(expect$verification, "verification records")
  for (index in rev(seq_along(records))) {
    record <- .require_object(records[[index]], "verification record")
    is_revoked <- any(vapply(revoked, .json_equal, logical(1), record))
    if (identical(record$canonical_form, 1L) &&
        identical(record$algorithm, "sha256") && !is_revoked) {
      return(record)
    }
  }
  .abort_category("unsupported-decoder", "no supported decoded-verification record")
}

.validate_representation <- function(dataset) {
  representation <- .require_object(dataset$representation, "dataset representation")
  decoder <- representation$decoder
  if (!identical(representation$decoder_version, 1L) ||
      !(decoder %in% c("delimited-text", "libsvm", "libsvm-split"))) {
    .abort_category(
      "unsupported-decoder",
      "R supports delimited-text, LIBSVM, and LIBSVM split version 1"
    )
  }
  roles <- if (identical(decoder, "libsvm-split")) c("train", "test") else "data"
  artifacts <- .representation_artifacts(dataset, representation, roles)
  options <- .require_object(representation$options, "representation options")
  compressions <- vapply(artifacts, function(artifact) {
    compression <- .require_string(artifact$compression, "artifact compression")
    if (!(compression %in% c("none", "gzip", "bzip2"))) {
      .abort_category("unsupported-decoder", "unsupported artifact compression")
    }
    compression
  }, character(1))
  formats <- vapply(
    artifacts,
    function(artifact) .require_string(artifact$format, "artifact format"),
    character(1)
  )
  if (identical(decoder, "delimited-text")) {
    if (!(formats[[1]] %in% c("csv", "tsv"))) {
      .abort_category("unsupported-decoder", "delimited-text requires CSV or TSV")
    }
    expected_delimiter <- if (identical(formats[[1]], "csv")) "," else "\t"
    if (!identical(options$delimiter, expected_delimiter)) {
      .abort_category("unsupported-decoder", "artifact format and delimiter disagree")
    }
  } else if (any(!(formats %in% c("libsvm", "svmlight")))) {
    .abort_category("unsupported-decoder", "LIBSVM decoder requires LIBSVM or SVMLight")
  }
  list(
    representation = representation,
    decoder = decoder,
    artifacts = artifacts,
    options = options,
    compressions = compressions
  )
}

#' Retrieve, verify, and decode one registered dataset
#'
#' @inheritParams fetch_artifact
#' @param verify_decoded Whether to verify expected shape and the canonical
#'   logical digest. Artifact verification cannot be disabled.
#' @param return_info Whether to return reproducibility metadata with the data.
#' @return An R data frame, `datamonger_sparse_dataset`, or
#'   `datamonger_sparse_dataset_split`. With `return_info = TRUE`, returns a
#'   `datamonger_fetch_result` containing `data` and `info`.
#' @export
fetch_data <- function(
    name,
    source,
    version = NULL,
    registry = NULL,
    cache_dir = NULL,
    offline = FALSE,
    verify_decoded = TRUE,
    return_info = FALSE) {
  for (argument in c("offline", "verify_decoded", "return_info")) {
    value <- get(argument, inherits = FALSE)
    if (!.is_scalar_logical(value)) {
      stop(paste0(argument, " must be TRUE or FALSE"), call. = FALSE)
    }
  }
  cache_dir <- .selected_cache_dir(cache_dir)
  registry <- .selected_registry(registry)
  index <- .load_registry(registry, cache_dir, offline)
  dataset <- .resolve_dataset(index, source, name, version)
  setup <- .validate_representation(dataset)

  leased <- list()
  on.exit({
    for (object in leased) .release_lock(object$lease)
  }, add = TRUE)
  for (artifact in setup$artifacts) {
    leased[[length(leased) + 1L]] <- .retrieve_artifact(
      artifact,
      cache_dir,
      offline
    )
  }
  paths <- vapply(leased, `[[`, character(1), "path")
  decoded <- switch(
    setup$decoder,
    `delimited-text` = .decode_delimited(
      paths[[1]], setup$options, setup$compressions[[1]]
    ),
    libsvm = .decode_libsvm(
      paths[[1]], setup$options, setup$compressions[[1]]
    ),
    `libsvm-split` = .decode_libsvm_split(
      paths[[1]],
      paths[[2]],
      setup$options,
      setup$compressions[[1]],
      setup$compressions[[2]]
    )
  )

  verification <- "artifact"
  canonical_form <- NULL
  canonical_digest <- NULL
  if (isTRUE(verify_decoded)) {
    expect <- .require_object(setup$representation$expect, "representation expectation")
    .validate_components(decoded$components, expect$components)
    record <- .verification_record(index, dataset, expect)
    canonical_form <- record$canonical_form
    expected_digest <- .require_string(record$digest, "canonical digest")
    canonical_digest <- .canonical_sha256(decoded$components)
    if (!identical(canonical_digest, expected_digest)) {
      .abort_category(
        "decoded-integrity",
        paste0(
          "decoded SHA-256 mismatch: expected ", expected_digest,
          ", received ", canonical_digest
        )
      )
    }
    verification <- "decoded"
  }

  artifact_digests <- vapply(setup$artifacts, `[[`, character(1), "sha256")
  names(artifact_digests) <- vapply(setup$artifacts, `[[`, character(1), "name")
  info <- structure(
    list(
      dataset_id = paste0(source, ":", name, "@", dataset$version),
      registry_release = registry$release,
      registry_index_sha256 = registry$index_sha256,
      artifact_digests = artifact_digests,
      verification = verification,
      canonical_form = canonical_form,
      canonical_digest = canonical_digest
    ),
    class = "datamonger_fetch_info"
  )
  if (isTRUE(return_info)) {
    return(structure(
      list(data = decoded$data, info = info),
      class = "datamonger_fetch_result"
    ))
  }
  decoded$data
}
