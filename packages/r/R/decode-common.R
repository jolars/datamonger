.new_int64 <- function(values, valid = !is.na(values)) {
  values[!valid] <- NA_character_
  structure(values, class = c("datamonger_int64", "character"))
}

.parse_binary64 <- function(value) {
  result <- dm_parse_binary64(value)
  if (is.null(result$category)) result$value else NULL
}

format.datamonger_int64 <- function(x, ...) unclass(x)

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
  if (rows <= .Machine$integer.max && columns <= .Machine$integer.max &&
      length(values) <= .Machine$integer.max) {
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

dim.datamonger_csr_matrix <- function(x) c(x$rows, x$columns)

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
