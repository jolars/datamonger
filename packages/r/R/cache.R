.cache_namespaces <- c("objects", "registries")

.cache_path <- function(cache_dir, namespace, digest) {
  if (!(namespace %in% .cache_namespaces)) {
    .abort_category("cache", paste0("unsupported cache namespace ", namespace))
  }
  if (!.is_scalar_character(digest) || !grepl(.sha256_pattern, digest, perl = TRUE)) {
    .abort_category("cache", "invalid cache SHA-256 digest")
  }
  file.path(cache_dir, namespace, "sha256", digest)
}

.lease_path <- function(cache_dir, namespace, digest, publication = FALSE) {
  suffix <- if (publication) ".publish.lock" else ".lock"
  file.path(
    cache_dir,
    ".leases",
    namespace,
    "sha256",
    paste0(digest, suffix)
  )
}

.create_directory <- function(path) {
  if (dir.exists(path)) {
    return(invisible(path))
  }
  ok <- tryCatch(
    dir.create(path, recursive = TRUE, showWarnings = FALSE),
    error = function(error) FALSE
  )
  if (!isTRUE(ok) && !dir.exists(path)) {
    .abort_category("cache", paste0("cannot create cache directory ", path))
  }
  invisible(path)
}

.acquire_lock <- function(path, exclusive, timeout = Inf) {
  .create_directory(dirname(path))
  tryCatch(
    filelock::lock(path, exclusive = exclusive, timeout = timeout),
    error = function(error) {
      message <- conditionMessage(error)
      if (identical(timeout, 0) &&
          grepl("already has|timed? out|timeout", message, ignore.case = TRUE)) {
        return(NULL)
      }
      .abort_category(
        "cache",
        paste0("cannot acquire cache lease ", path, ": ", message)
      )
    }
  )
}

.release_lock <- function(lock) {
  if (is.null(lock)) {
    return(invisible(NULL))
  }
  tryCatch(
    filelock::unlock(lock),
    error = function(error) {
      .abort_category(
        "cache",
        paste0("cannot release cache lease: ", conditionMessage(error))
      )
    }
  )
  invisible(NULL)
}

.matches_cache_object <- function(path, digest, size = NULL) {
  if (!file.exists(path) || isTRUE(file.info(path)$isdir)) {
    return(FALSE)
  }
  actual_size <- file.info(path)$size
  actual_digest <- tryCatch(
    .sha256_file(path),
    error = function(error) {
      .abort_category(
        "cache",
        paste0("cannot inspect cached object ", path, ": ", conditionMessage(error))
      )
    }
  )
  identical(actual_digest, digest) &&
    (is.null(size) || identical(as.numeric(actual_size), as.numeric(size)))
}

.decode_http_gzip <- function(contents, url) {
  if (length(contents) < 18L ||
      !identical(contents[1:3], as.raw(c(0x1f, 0x8b, 0x08)))) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("malformed gzip content coding from ", url)
    )
  }
  flags <- as.integer(contents[[4]])
  if (bitwAnd(flags, 0xe0L) != 0L) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("malformed gzip flags from ", url)
    )
  }
  tryCatch(
    .Call(C_dm_gzip_decompress, contents),
    error = function(error) {
      .dm_abort(
        "datamonger_retrieval_exhausted",
        paste0(
          "malformed gzip content coding from ", url, ": ",
          conditionMessage(error)
        )
      )
    }
  )
}

.final_headers <- function(headers) {
  text <- rawToChar(headers)
  blocks <- strsplit(text, "\r\n\r\n", fixed = TRUE)[[1]]
  blocks <- blocks[nzchar(blocks)]
  if (!length(blocks)) {
    return(list())
  }
  lines <- strsplit(tail(blocks, 1L), "\r\n", fixed = TRUE)[[1]]
  if (!grepl("^HTTP/[0-9.]+ [0-9]{3}(?: |$)", lines[[1]], perl = TRUE)) {
    .dm_abort("datamonger_retrieval_exhausted", "malformed HTTP response headers")
  }
  result <- list()
  for (line in lines[-1L]) {
    match <- regexec("^([^:[:space:]]+):[[:space:]]*(.*)$", line, perl = TRUE)
    fields <- regmatches(line, match)[[1]]
    if (length(fields) != 3L) {
      .dm_abort("datamonger_retrieval_exhausted", "malformed HTTP response header")
    }
    name <- tolower(fields[[2]])
    result[[name]] <- c(result[[name]], fields[[3]])
  }
  result
}

.header_tokens <- function(headers, name) {
  values <- headers[[name]]
  if (is.null(values)) {
    return(character())
  }
  trimws(unlist(strsplit(values, ",", fixed = TRUE), use.names = FALSE))
}

.validate_transport_headers <- function(headers, encoded_size, url) {
  lengths <- .header_tokens(headers, "content-length")
  if (length(lengths)) {
    if (any(!grepl("^[0-9]+$", lengths)) || length(unique(lengths)) != 1L) {
      .dm_abort(
        "datamonger_retrieval_exhausted",
        paste0("malformed or conflicting Content-Length from ", url)
      )
    }
    if (as.numeric(lengths[[1]]) != encoded_size) {
      .dm_abort(
        "datamonger_retrieval_exhausted",
        paste0("truncated HTTP response from ", url)
      )
    }
  }
  transfer <- tolower(.header_tokens(headers, "transfer-encoding"))
  if (length(transfer) && !identical(transfer, "chunked")) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("unsupported HTTP transfer coding from ", url)
    )
  }
}

.download_url_to_file <- function(url, path, require_https = FALSE) {
  if (!.is_http_url(url, https_only = require_https)) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("invalid retrieval URL ", url)
    )
  }
  handle <- curl::new_handle(
    followlocation = TRUE,
    timeout = 30,
    http_content_decoding = FALSE,
    http_transfer_decoding = TRUE,
    failonerror = FALSE
  )
  curl::handle_setheaders(handle, "Accept-Encoding" = "identity")
  response <- tryCatch(
    curl::curl_fetch_disk(url, path, handle = handle),
    error = function(error) {
      .dm_abort(
        "datamonger_retrieval_exhausted",
        paste0("cannot retrieve ", url, ": ", conditionMessage(error))
      )
    }
  )
  if (response$status_code < 200L || response$status_code >= 300L) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("HTTP ", response$status_code, " while retrieving ", url)
    )
  }
  if (!.is_http_url(response$url, https_only = require_https)) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("retrieval redirected to an invalid URL: ", response$url)
    )
  }
  headers <- .final_headers(response$headers)
  encoded_size <- file.info(path)$size
  .validate_transport_headers(headers, encoded_size, url)
  codings <- tolower(.header_tokens(headers, "content-encoding"))
  non_identity <- codings[codings != "identity"]
  if (any(!nzchar(codings)) || length(non_identity) > 1L ||
      (length(non_identity) && !(non_identity %in% c("gzip", "x-gzip")))) {
    .dm_abort(
      "datamonger_retrieval_exhausted",
      paste0("unsupported HTTP content coding from ", url)
    )
  }
  if (length(non_identity)) {
    decoded <- .decode_http_gzip(.read_raw(path), url)
    .write_raw(decoded, path)
  }
  invisible(path)
}

.retrieve_url_raw <- function(
    url,
    require_https = FALSE,
    class = "datamonger_registry_retrieval") {
  path <- tempfile("datamonger-http-")
  on.exit(unlink(path), add = TRUE)
  tryCatch(
    .download_url_to_file(url, path, require_https = require_https),
    datamonger_retrieval_exhausted = function(error) {
      .dm_abort(class, conditionMessage(error))
    }
  )
  .read_raw(path, "datamonger_registry_retrieval")
}

.discard_cache_object <- function(path) {
  if (file.exists(path) && !isTRUE(unlink(path) == 0L)) {
    .abort_category("cache", paste0("cannot discard invalid cache object ", path))
  }
}

.publish_download <- function(
    cache_dir,
    namespace,
    digest,
    size,
    urls,
    integrity_class,
    retrieval_class) {
  target <- .cache_path(cache_dir, namespace, digest)
  .create_directory(dirname(target))
  failures <- character()
  integrity_failure <- FALSE

  for (url in urls) {
    temporary <- tempfile(".download-", tmpdir = dirname(target))
    succeeded <- FALSE
    tryCatch(
      {
        .download_url_to_file(url, temporary)
        actual_size <- file.info(temporary)$size
        actual_digest <- .sha256_file(temporary)
        if ((!is.null(size) && actual_size != size) ||
            !identical(actual_digest, digest)) {
          integrity_failure <- TRUE
          stop(structure(
            list(message = paste0("artifact bytes from ", url, " failed integrity")),
            class = c("datamonger_location_failure", "error", "condition")
          ))
        }

        publication <- .acquire_lock(
          .lease_path(cache_dir, namespace, digest, publication = TRUE),
          exclusive = TRUE
        )
        on.exit(.release_lock(publication), add = TRUE, after = FALSE)
        if (!.matches_cache_object(target, digest, size)) {
          .discard_cache_object(target)
          if (!file.rename(temporary, target)) {
            .abort_category("cache", paste0("cannot publish cache object ", target))
          }
        }
        .release_lock(publication)
        publication <- NULL
        succeeded <- TRUE
      },
      datamonger_cache = function(error) stop(error),
      datamonger_location_failure = function(error) {
        failures <<- c(failures, conditionMessage(error))
      },
      datamonger_retrieval_exhausted = function(error) {
        failures <<- c(failures, paste0(url, ": ", conditionMessage(error)))
      }
    )
    unlink(temporary)
    if (succeeded) {
      return(target)
    }
  }
  class <- if (integrity_failure) integrity_class else retrieval_class
  .dm_abort(
    class,
    paste0("all retrieval locations failed: ", paste(failures, collapse = "; ")),
    locations = urls
  )
}

.retrieve_cached_object <- function(
    cache_dir,
    namespace,
    digest,
    size,
    urls,
    offline,
    integrity_class,
    offline_class,
    retrieval_class) {
  target <- .cache_path(cache_dir, namespace, digest)
  lease <- .acquire_lock(
    .lease_path(cache_dir, namespace, digest),
    exclusive = FALSE
  )
  if (.matches_cache_object(target, digest, size)) {
    return(list(path = target, lease = lease))
  }
  .discard_cache_object(target)
  if (isTRUE(offline)) {
    .release_lock(lease)
    .dm_abort(offline_class, paste0("no valid cached object for ", digest))
  }
  path <- tryCatch(
    .publish_download(
      cache_dir,
      namespace,
      digest,
      size,
      urls,
      integrity_class,
      retrieval_class
    ),
    error = function(error) {
      .release_lock(lease)
      stop(error)
    }
  )
  list(path = path, lease = lease)
}
