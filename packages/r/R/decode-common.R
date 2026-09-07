.int64_pattern <- "^-?(0|[1-9][0-9]*)$"
.signed_int64_pattern <- "^[+-]?(0|[1-9][0-9]*)$"
.float_pattern <- "^[+-]?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?$"
.delimited_float_pattern <- "^-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?$"

.int64_in_range <- function(value) {
  negative <- startsWith(value, "-")
  unsigned <- sub("^[+-]", "", value)
  limit <- if (negative) "9223372036854775808" else "9223372036854775807"
  nchar(unsigned) < nchar(limit) ||
    (nchar(unsigned) == nchar(limit) && unsigned <= limit)
}

.normalize_int64 <- function(value, allow_plus = FALSE) {
  pattern <- if (allow_plus) .signed_int64_pattern else .int64_pattern
  if (!grepl(pattern, value, perl = TRUE) || !.int64_in_range(value)) {
    return(NULL)
  }
  if (startsWith(value, "+")) {
    substring(value, 2L)
  } else {
    value
  }
}

.new_int64 <- function(values, valid = !is.na(values)) {
  values[!valid] <- NA_character_
  structure(values, class = c("datamonger_int64", "character"))
}

.parse_binary64 <- function(value) {
  json_number <- sub("^\\+", "", value)
  parsed <- tryCatch(
    jsonlite::fromJSON(json_number, simplifyVector = TRUE),
    error = function(error) NA_real_
  )
  if (!is.numeric(parsed) || length(parsed) != 1L || !is.finite(parsed)) {
    return(NULL)
  }
  parsed <- as.numeric(parsed)
  if (parsed == 0 && startsWith(value, "-")) {
    parsed <- -parsed
  }
  parsed
}

format.datamonger_int64 <- function(x, ...) {
  unclass(x)
}

print.datamonger_int64 <- function(x, ...) {
  print(format(x), quote = FALSE, ...)
  invisible(x)
}

.decompress_artifact <- function(path, compression) {
  contents <- .read_raw(path)
  if (identical(compression, "none")) {
    return(contents)
  }
  if (!(compression %in% c("gzip", "bzip2"))) {
    .abort_category(
      "unsupported-decoder",
      paste0("unsupported artifact compression '", compression, "'")
    )
  }
  tryCatch(
    memDecompress(contents, type = compression),
    error = function(error) {
      .abort_category(
        "decode",
        paste0("cannot decompress verified artifact: ", conditionMessage(error))
      )
    }
  )
}

.utf8_text <- function(contents, description = "artifact") {
  if (length(contents) >= 3L &&
      identical(contents[seq_len(3L)], as.raw(c(0xef, 0xbb, 0xbf)))) {
    .abort_category("decode", paste0(description, " has a UTF-8 byte-order mark"))
  }
  text <- tryCatch(
    rawToChar(contents),
    error = function(error) .abort_category("decode", paste0(description, " is not valid UTF-8"))
  )
  validated <- iconv(text, from = "UTF-8", to = "UTF-8", sub = NA_character_)
  if (is.na(validated)) {
    .abort_category("decode", paste0(description, " is not valid UTF-8"))
  }
  Encoding(validated) <- "UTF-8"
  validated
}

.strict_records <- function(contents, allow_empty) {
  if (!length(contents)) {
    if (allow_empty) {
      return(character())
    }
    .abort_category("decode", "artifact is empty")
  }
  text <- .utf8_text(contents)
  text <- gsub("\r\n", "\n", text, fixed = TRUE)
  if (grepl("\r", text, fixed = TRUE)) {
    .abort_category("decode", "artifact contains a bare carriage return")
  }
  terminated <- endsWith(text, "\n")
  if (terminated) {
    text <- substr(text, 1L, nchar(text, type = "chars") - 1L)
  }
  records <- if (!nzchar(text)) "" else strsplit(text, "\n", fixed = TRUE)[[1]]
  records
}

.vector_component <- function(name, type, values, valid) {
  structure(
    list(
      name = name,
      kind = "vector",
      logical_type = type,
      values = values,
      valid = as.logical(valid)
    ),
    class = "datamonger_logical_component"
  )
}

.sparse_component <- function(
    name,
    rows,
    columns,
    row_offsets,
    column_indices,
    values) {
  structure(
    list(
      name = name,
      kind = "sparse_matrix",
      logical_type = "float64",
      rows = rows,
      columns = columns,
      row_offsets = row_offsets,
      column_indices = column_indices,
      values = values
    ),
    class = "datamonger_logical_component"
  )
}

.native_sparse_matrix <- function(
    rows,
    columns,
    row_offsets,
    column_indices,
    values) {
  if (rows <= .Machine$integer.max && columns <= .Machine$integer.max) {
    return(Matrix::sparseMatrix(
      i = rep(seq_len(rows), diff(row_offsets)),
      j = column_indices + 1,
      x = values,
      dims = c(rows, columns),
      index1 = TRUE,
      repr = "R"
    ))
  }
  structure(
    list(
      rows = rows,
      columns = columns,
      row_offsets = row_offsets,
      column_indices = column_indices,
      values = values
    ),
    class = "datamonger_csr_matrix"
  )
}

dim.datamonger_csr_matrix <- function(x) {
  c(x$rows, x$columns)
}

print.datamonger_csr_matrix <- function(x, ...) {
  cat(
    "<datamonger_csr_matrix> ",
    x$rows,
    " x ",
    x$columns,
    " with ",
    length(x$values),
    " stored values\n",
    sep = ""
  )
  invisible(x)
}
