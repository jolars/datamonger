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
  if (
    !.is_scalar_character(options$delimiter) ||
      !(options$delimiter %in% c(",", "\t"))
  ) {
    .abort_category("unsupported-decoder", "unsupported delimiter")
  }
  missing_values <- options$missing_values %||% list()
  .require_array(
    missing_values,
    "missing_values",
    "datamonger_unsupported_decoder"
  )
  if (
    !all(vapply(missing_values, .is_scalar_character, logical(1))) ||
      anyDuplicated(unlist(missing_values, use.names = FALSE))
  ) {
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
    if (
      !.is_scalar_character(column$name) ||
        !nzchar(column$name) ||
        !.is_scalar_character(column$type) ||
        !(column$type %in% c("float64", "int64", "string", "bool"))
    ) {
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

.decode_delimited <- function(
  path,
  options,
  compression = "none",
  hash = FALSE
) {
  options <- .validate_delimited_options(options)
  decoded <- .native_result(dm_decode(
    "delimited-text",
    path,
    compression,
    options,
    hash
  ))
  columns <- lapply(decoded$components, .public_vector)
  names(columns) <- vapply(decoded$components, `[[`, character(1), "name")
  decoded$data <- structure(
    columns,
    row.names = seq_along(columns[[1]]),
    class = "data.frame"
  )
  decoded
}
