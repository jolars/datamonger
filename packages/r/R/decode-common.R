.new_int64 <- function(values, valid = !is.na(values)) {
  values[!valid] <- NA_character_
  structure(values, class = c("datamonger_int64", "character"))
}

.parse_binary64 <- function(value) {
  result <- dm_parse_binary64(value)
  if (is.null(result$category)) result$value else NULL
}

#' Display Exact 64-bit Integer Values
#'
#' Datamonger stores signed 64-bit integers as decimal character strings so that
#' values outside R's exact numeric range retain all their digits. These methods
#' display those strings without converting them to floating-point numbers.
#'
#' @param x A `datamonger_int64` vector returned in decoded data.
#' @param ... For `print()`, additional arguments passed to the character vector
#'   print method, except `quote`, which is fixed to `FALSE`. The format method
#'   ignores these arguments.
#' @details
#' Missing values are stored as `NA_character_`. The format method removes the
#' Datamonger class and retains the underlying strings and missing values. The
#' print method displays the formatted vector without quotation marks.
#'
#' @returns
#' `format()` returns the underlying character vector. `print()` returns `x`
#' invisibly.
#'
#' @seealso [fetch_data()]
#'
#' @name datamonger_int64
#' @rdname int64
#' @exportS3Method format datamonger_int64
format.datamonger_int64 <- function(x, ...) {
  unclass(x)
}

#' @rdname int64
#' @exportS3Method print datamonger_int64
print.datamonger_int64 <- function(x, ...) {
  print(format(x), quote = FALSE, ...)
  invisible(x)
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
  values
) {
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
  values
) {
  if (
    rows <= .Machine$integer.max &&
      columns <= .Machine$integer.max &&
      length(values) <= .Machine$integer.max
  ) {
    return(Matrix::sparseMatrix(
      p = as.integer(row_offsets),
      j = as.integer(column_indices),
      x = values,
      dims = c(rows, columns),
      index1 = FALSE,
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

#' Inspect a Sparse Matrix with Large Dimensions
#'
#' Datamonger normally returns sparse features as a row-compressed `Matrix`.
#' When a declared dimension exceeds the `Matrix` integer limit, it returns a
#' `datamonger_csr_matrix` that retains the exact dimensions and CSR arrays.
#' These methods report its dimensions and a compact summary without allocating
#' a dense matrix.
#'
#' @param x A `datamonger_csr_matrix` returned as sparse dataset features.
#' @param ... Additional arguments, ignored by the print method.
#' @details
#' The object contains `rows` and `columns`, zero-based `row_offsets` and
#' `column_indices`, and float64 `values`. The print method reports the
#' dimensions and the number of stored values.
#'
#' @returns
#' `dim()` returns a numeric vector containing the row and column counts, in
#' that order. `print()` returns `x` invisibly.
#'
#' @seealso [fetch_data()]
#'
#' @name datamonger_csr_matrix
#' @rdname csr-matrix
#' @exportS3Method dim datamonger_csr_matrix
dim.datamonger_csr_matrix <- function(x) {
  c(x$rows, x$columns)
}

#' @rdname csr-matrix
#' @exportS3Method print datamonger_csr_matrix
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
