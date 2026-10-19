.canonical_bytes <- function(components) {
  .native_result(dm_canonical(components, FALSE))
}

.canonical_sha256 <- function(components) {
  .native_result(dm_canonical(components, TRUE))
}

.descriptor_value <- function(value) {
  if (.is_scalar_character(value)) {
    if (identical(value, "-zero")) {
      return(-0)
    }
    if (identical(value, "nan")) {
      return(NaN)
    }
    if (identical(value, "invalid")) return(0)
  }
  value
}

.component_from_descriptor <- function(descriptor) {
  kind <- descriptor$kind
  type <- descriptor$type
  values <- lapply(descriptor$values, .descriptor_value)
  if (identical(type, "string") || identical(type, "int64")) {
    values <- vapply(values, as.character, character(1))
  } else if (identical(type, "bool")) {
    values <- as.logical(unlist(values, use.names = FALSE))
  } else {
    values <- as.numeric(unlist(values, use.names = FALSE))
  }
  if (identical(kind, "vector")) {
    return(.vector_component(
      descriptor$name,
      type,
      values,
      as.logical(unlist(descriptor$valid, use.names = FALSE))
    ))
  }
  if (identical(kind, "dense_matrix")) {
    return(structure(
      list(
        name = descriptor$name,
        kind = kind,
        logical_type = type,
        rows = descriptor$rows,
        columns = descriptor$columns,
        values = values,
        valid = as.logical(unlist(descriptor$valid, use.names = FALSE))
      ),
      class = "datamonger_logical_component"
    ))
  }
  .sparse_component(
    descriptor$name,
    descriptor$rows,
    descriptor$columns,
    as.numeric(unlist(descriptor$row_offsets, use.names = FALSE)),
    as.numeric(unlist(descriptor$column_indices, use.names = FALSE)),
    values
  )
}
