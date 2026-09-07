.validate_delimited_options <- function(options) {
  .require_object(options, "decoder options", "datamonger_unsupported_decoder")
  supported <- c(
    "encoding",
    "delimiter",
    "header",
    "quote",
    "escape",
    "missing_values",
    "row_order",
    "columns"
  )
  required <- setdiff(supported, "missing_values")
  unknown <- setdiff(names(options), supported)
  missing <- setdiff(required, names(options))
  if (length(unknown)) {
    .abort_category(
      "unsupported-decoder",
      paste0("unsupported decoder options: ", paste(unknown, collapse = ", "))
    )
  }
  if (length(missing)) {
    .abort_category(
      "unsupported-decoder",
      paste0("missing decoder options: ", paste(missing, collapse = ", "))
    )
  }
  expected <- list(
    encoding = "utf-8",
    header = TRUE,
    quote = "\"",
    escape = "double",
    row_order = "source"
  )
  for (name in names(expected)) {
    if (!identical(options[[name]], expected[[name]])) {
      .abort_category(
        "unsupported-decoder",
        paste0("unsupported ", name, " option")
      )
    }
  }
  if (!.is_scalar_character(options$delimiter) ||
      !(options$delimiter %in% c(",", "\t"))) {
    .abort_category("unsupported-decoder", "unsupported delimiter")
  }
  missing_values <- options$missing_values %||% list()
  .require_array(
    missing_values,
    "missing_values",
    "datamonger_unsupported_decoder"
  )
  if (any(!vapply(missing_values, .is_scalar_character, logical(1))) ||
      anyDuplicated(unlist(missing_values, use.names = FALSE))) {
    .abort_category(
      "unsupported-decoder",
      "missing values must be unique strings"
    )
  }
  columns <- .require_array(
    options$columns,
    "columns",
    "datamonger_unsupported_decoder"
  )
  parsed <- lapply(columns, function(column) {
    .require_exact_fields(
      column,
      c("name", "type"),
      "column",
      "datamonger_unsupported_decoder"
    )
    if (!.is_scalar_character(column$name) || !nzchar(column$name) ||
        !.is_scalar_character(column$type) ||
        !(column$type %in% c("float64", "int64", "string", "bool"))) {
      .abort_category("unsupported-decoder", "column name or type is invalid")
    }
    column
  })
  names <- vapply(parsed, `[[`, character(1), "name")
  if (!length(parsed) || anyDuplicated(names)) {
    .abort_category(
      "unsupported-decoder",
      "column names must be nonempty and unique"
    )
  }
  list(
    columns = parsed,
    missing_values = unlist(missing_values, use.names = FALSE),
    delimiter = options$delimiter
  )
}

`%||%` <- function(left, right) {
  if (is.null(left)) right else left
}

.raw_field_text <- function(bytes) {
  .utf8_text(as.raw(bytes), "delimited field")
}

.parse_delimited_records <- function(contents, delimiter) {
  if (!length(contents)) {
    .abort_category("decode", "delimited artifact is empty")
  }
  if (length(contents) >= 3L &&
      identical(contents[seq_len(3L)], as.raw(c(0xef, 0xbb, 0xbf)))) {
    .abort_category("decode", "delimited artifact has a UTF-8 byte-order mark")
  }
  delimiter_byte <- as.integer(charToRaw(delimiter))
  quote_byte <- as.integer(charToRaw("\""))
  bytes <- as.integer(contents)
  records <- list()
  fields <- list()
  field <- integer()
  state <- "start"
  index <- 1L

  finish_field <- function() {
    fields[[length(fields) + 1L]] <<- .raw_field_text(field)
    field <<- integer()
    state <<- "start"
  }
  finish_record <- function() {
    finish_field()
    records[[length(records) + 1L]] <<- fields
    fields <<- list()
  }

  while (index <= length(bytes)) {
    byte <- bytes[[index]]
    if (identical(state, "quoted")) {
      if (byte == quote_byte) {
        if (index < length(bytes) && bytes[[index + 1L]] == quote_byte) {
          field <- c(field, quote_byte)
          index <- index + 2L
          next
        }
        state <- "after_quote"
        index <- index + 1L
        next
      }
      if (byte %in% c(10L, 13L)) {
        .abort_category("decode", "quoted field contains a line break")
      }
      field <- c(field, byte)
      index <- index + 1L
      next
    }

    if (identical(state, "after_quote") &&
        !(byte %in% c(delimiter_byte, 10L, 13L))) {
      .abort_category("decode", "closing quote has a trailing suffix")
    }
    if (byte == quote_byte) {
      if (!identical(state, "start")) {
        .abort_category("decode", "unquoted field contains a quote")
      }
      state <- "quoted"
    } else if (byte == delimiter_byte) {
      finish_field()
    } else if (byte %in% c(10L, 13L)) {
      if (byte == 13L) {
        if (index == length(bytes) || bytes[[index + 1L]] != 10L) {
          .abort_category("decode", "artifact contains a bare carriage return")
        }
        index <- index + 1L
      }
      finish_record()
    } else {
      if (identical(state, "after_quote")) {
        .abort_category("decode", "closing quote has a trailing suffix")
      }
      state <- "unquoted"
      field <- c(field, byte)
    }
    index <- index + 1L
  }
  if (identical(state, "quoted")) {
    .abort_category("decode", "unterminated quoted field")
  }
  if (length(field) || length(fields) || !tail(bytes, 1L) %in% c(10L, 13L)) {
    finish_record()
  }
  records
}

.parse_delimited_value <- function(value, type, row, column) {
  if (identical(type, "string")) {
    return(value)
  }
  if (identical(type, "bool")) {
    if (identical(value, "true")) return(TRUE)
    if (identical(value, "false")) return(FALSE)
    .abort_category(
      "decode",
      paste0("invalid bool at row ", row, ", column '", column, "'")
    )
  }
  if (identical(type, "int64")) {
    parsed <- .normalize_int64(value)
    if (is.null(parsed)) {
      .abort_category(
        "decode",
        paste0("invalid int64 at row ", row, ", column '", column, "'")
      )
    }
    return(parsed)
  }
  if (!grepl(.delimited_float_pattern, value, perl = TRUE)) {
    .abort_category(
      "decode",
      paste0("invalid float64 at row ", row, ", column '", column, "'")
    )
  }
  parsed <- .parse_binary64(value)
  if (is.null(parsed)) {
    .abort_category(
      "decode",
      paste0("non-finite float64 at row ", row, ", column '", column, "'")
    )
  }
  parsed
}

.decode_delimited <- function(path, options, compression = "none") {
  validated <- .validate_delimited_options(options)
  records <- .parse_delimited_records(
    .decompress_artifact(path, compression),
    validated$delimiter
  )
  expected_names <- vapply(validated$columns, `[[`, character(1), "name")
  if (!identical(unlist(records[[1]], use.names = FALSE), expected_names)) {
    .abort_category("decode", "artifact header does not match declared columns")
  }
  rows <- records[-1L]
  if (any(vapply(rows, length, integer(1)) != length(expected_names))) {
    .abort_category("decode", "data record has the wrong number of fields")
  }

  components <- vector("list", length(validated$columns))
  data_columns <- vector("list", length(validated$columns))
  for (column_index in seq_along(validated$columns)) {
    column <- validated$columns[[column_index]]
    raw_values <- vapply(
      rows,
      function(row) row[[column_index]],
      character(1)
    )
    valid <- !(raw_values %in% validated$missing_values)
    values <- switch(
      column$type,
      float64 = numeric(length(rows)),
      int64 = rep("0", length(rows)),
      string = rep("", length(rows)),
      bool = logical(length(rows))
    )
    for (row_index in which(valid)) {
      values[[row_index]] <- .parse_delimited_value(
        raw_values[[row_index]],
        column$type,
        row_index,
        column$name
      )
    }
    components[[column_index]] <- .vector_component(
      column$name,
      column$type,
      values,
      valid
    )
    public <- values
    if (identical(column$type, "int64")) {
      public <- .new_int64(public, valid)
    } else {
      public[!valid] <- NA
    }
    data_columns[[column_index]] <- public
  }
  names(data_columns) <- expected_names
  data <- structure(
    data_columns,
    names = expected_names,
    row.names = seq_len(length(rows)),
    class = "data.frame"
  )
  list(data = data, components = components)
}
