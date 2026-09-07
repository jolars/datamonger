.sha256_pattern <- "^[0-9a-f]{64}$"
.identifier_pattern <- "^[a-z0-9][a-z0-9._-]*$"
.version_pattern <- "^[A-Za-z0-9][A-Za-z0-9._+-]*$"
.release_pattern <- .identifier_pattern
.dataset_id_pattern <- paste0(
  "[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*@",
  "[A-Za-z0-9][A-Za-z0-9._+-]*"
)
.max_exact_integer <- 9007199254740991

.is_scalar_character <- function(value) {
  is.character(value) && length(value) == 1L && !is.na(value)
}

.is_scalar_logical <- function(value) {
  is.logical(value) && length(value) == 1L && !is.na(value)
}

.is_exact_number <- function(value, minimum = 0) {
  is.numeric(value) &&
    length(value) == 1L &&
    !is.na(value) &&
    is.finite(value) &&
    value == floor(value) &&
    value >= minimum &&
    value <= .max_exact_integer
}

.is_http_url <- function(value, https_only = FALSE) {
  if (!.is_scalar_character(value)) {
    return(FALSE)
  }
  allowed_prefix <- if (https_only) {
    startsWith(value, "https://")
  } else {
    startsWith(value, "http://") || startsWith(value, "https://")
  }
  if (!allowed_prefix) {
    return(FALSE)
  }
  parsed <- tryCatch(
    curl::curl_parse_url(value, default_scheme = FALSE),
    error = function(error) NULL
  )
  !is.null(parsed) && nzchar(parsed$host) &&
    parsed$scheme %in% if (https_only) "https" else c("http", "https")
}

.json_equal <- function(left, right) {
  if (is.numeric(left) && is.numeric(right)) {
    return(identical(as.numeric(left), as.numeric(right)))
  }
  if (is.list(left) && is.list(right)) {
    left_names <- names(left)
    right_names <- names(right)
    if (is.null(left_names) != is.null(right_names) || length(left) != length(right)) {
      return(FALSE)
    }
    if (is.null(left_names)) {
      return(all(vapply(
        seq_along(left),
        function(index) .json_equal(left[[index]], right[[index]]),
        logical(1)
      )))
    }
    if (!setequal(left_names, right_names)) {
      return(FALSE)
    }
    return(all(vapply(
      left_names,
      function(name) .json_equal(left[[name]], right[[name]]),
      logical(1)
    )))
  }
  identical(left, right)
}

.is_object <- function(value) {
  is.list(value) && !is.null(names(value))
}

.require_object <- function(value, field, class = "datamonger_unsupported_registry") {
  if (!.is_object(value)) {
    .dm_abort(class, paste0(field, " must be an object"))
  }
  value
}

.require_array <- function(value, field, class = "datamonger_unsupported_registry") {
  if (!is.list(value) || !is.null(names(value))) {
    .dm_abort(class, paste0(field, " must be an array"))
  }
  value
}

.require_string <- function(value, field, class = "datamonger_unsupported_registry") {
  if (!.is_scalar_character(value)) {
    .dm_abort(class, paste0(field, " must be a string"))
  }
  value
}

.require_integer <- function(value, field, class = "datamonger_unsupported_registry") {
  if (!.is_exact_number(value)) {
    .dm_abort(class, paste0(field, " must be an exact nonnegative JSON integer"))
  }
  value
}

.require_exact_fields <- function(value, fields, field, class) {
  .require_object(value, field, class)
  if (!identical(sort(names(value)), sort(fields))) {
    .dm_abort(
      class,
      paste0(field, " must contain exactly: ", paste(fields, collapse = ", "))
    )
  }
  value
}

.read_raw <- function(path, class = "datamonger_cache") {
  tryCatch(
    {
      size <- file.info(path)$size
      if (is.na(size)) {
        stop("file is unavailable")
      }
      readBin(path, "raw", n = size)
    },
    error = function(error) {
      .dm_abort(class, paste0("cannot read ", path, ": ", conditionMessage(error)))
    }
  )
}

.write_raw <- function(contents, path, class = "datamonger_cache") {
  tryCatch(
    {
      connection <- file(path, open = "wb")
      on.exit(close(connection), add = TRUE)
      writeBin(contents, connection)
      flush(connection)
    },
    error = function(error) {
      .dm_abort(class, paste0("cannot write ", path, ": ", conditionMessage(error)))
    }
  )
  invisible(path)
}

.parse_json_raw <- function(contents, description, class = "datamonger_registry") {
  if (length(contents) >= 3L && identical(contents[seq_len(3L)], as.raw(c(0xef, 0xbb, 0xbf)))) {
    .dm_abort(class, paste0(description, " must be UTF-8 without a byte-order mark"))
  }
  text <- tryCatch(
    rawToChar(contents),
    error = function(error) {
      .dm_abort(class, paste0(description, " is not valid UTF-8 JSON"))
    }
  )
  if (is.na(iconv(text, from = "UTF-8", to = "UTF-8", sub = NA_character_))) {
    .dm_abort(class, paste0(description, " is not valid UTF-8 JSON"))
  }
  tryCatch(
    jsonlite::fromJSON(text, simplifyVector = FALSE, bigint_as_char = TRUE),
    error = function(error) {
      .dm_abort(
        class,
        paste0(description, " contains invalid JSON: ", conditionMessage(error))
      )
    }
  )
}

.sha256_raw <- function(contents) {
  digest::digest(contents, algo = "sha256", serialize = FALSE)
}

.sha256_file <- function(path) {
  digest::digest(file = path, algo = "sha256", serialize = FALSE)
}

.hex_to_raw <- function(value) {
  if (!.is_scalar_character(value) || nchar(value, type = "bytes") %% 2L != 0L ||
      grepl("[^0-9a-fA-F]", value)) {
    stop("invalid hexadecimal string", call. = FALSE)
  }
  if (!nzchar(value)) {
    return(raw())
  }
  as.raw(strtoi(substring(
    value,
    seq.int(1L, nchar(value), 2L),
    seq.int(2L, nchar(value), 2L)
  ), 16L))
}
