.pack_unsigned <- function(value, bytes) {
  if (!.is_exact_number(value) || value >= 256^bytes) {
    .abort_category("decoded-integrity", "canonical framing integer is out of range")
  }
  result <- raw(bytes)
  remaining <- value
  for (index in seq_len(bytes)) {
    result[[index]] <- as.raw(remaining %% 256)
    remaining <- floor(remaining / 256)
  }
  result
}

.pack_u16 <- function(value) .pack_unsigned(value, 2L)
.pack_u32 <- function(value) .pack_unsigned(value, 4L)
.pack_u64 <- function(value) .pack_unsigned(value, 8L)

.pack_int64 <- function(value) {
  normalized <- .normalize_int64(as.character(value), allow_plus = TRUE)
  if (is.null(normalized)) {
    .abort_category("decoded-integrity", "canonical int64 value is out of range")
  }
  negative <- startsWith(normalized, "-")
  digits <- strtoi(strsplit(sub("^-", "", normalized), "", fixed = TRUE)[[1]])
  bytes <- integer(8L)
  for (digit in digits) {
    carry <- digit
    for (index in seq_len(8L)) {
      current <- bytes[[index]] * 10 + carry
      bytes[[index]] <- current %% 256L
      carry <- current %/% 256L
    }
    if (carry != 0L) {
      .abort_category("decoded-integrity", "canonical int64 value is out of range")
    }
  }
  if (negative) {
    bytes <- 255L - bytes
    carry <- 1L
    for (index in seq_len(8L)) {
      current <- bytes[[index]] + carry
      bytes[[index]] <- current %% 256L
      carry <- current %/% 256L
    }
  }
  as.raw(bytes)
}

.bitmap <- function(values) {
  result <- raw(ceiling(length(values) / 8))
  for (index in which(values)) {
    byte <- (index - 1L) %/% 8L + 1L
    bit <- (index - 1L) %% 8L
    result[[byte]] <- as.raw(bitwOr(as.integer(result[[byte]]), bitwShiftL(1L, bit)))
  }
  result
}

.float_bytes <- function(value, valid) {
  if (!valid) {
    return(raw(8L))
  }
  if (is.nan(value)) {
    return(as.raw(c(0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xf8, 0x7f)))
  }
  if (value == 0) {
    return(raw(8L))
  }
  if (!is.finite(value)) {
    .abort_category("decoded-integrity", "canonical float64 value is infinite")
  }
  writeBin(as.double(value), raw(), size = 8L, endian = "little")
}

.utf8_bytes <- function(value) {
  if (!.is_scalar_character(value)) {
    .abort_category("decoded-integrity", "canonical string must be a scalar string")
  }
  converted <- iconv(value, from = "UTF-8", to = "UTF-8", sub = NA_character_)
  if (is.na(converted)) {
    .abort_category("decoded-integrity", "canonical string is not valid UTF-8")
  }
  charToRaw(enc2utf8(converted))
}

.canonical_values <- function(component, valid) {
  values <- component$values
  type <- component$logical_type
  if (length(values) != length(valid)) {
    .abort_category("decoded-integrity", "component values and validity disagree")
  }
  if (identical(type, "bool")) {
    return(.bitmap(as.logical(values) & valid))
  }
  parts <- lapply(seq_along(values), function(index) {
    switch(
        type,
        float64 = .float_bytes(values[[index]], valid[[index]]),
        int64 = .pack_int64(if (valid[[index]]) values[[index]] else "0"),
        string = {
          bytes <- if (valid[[index]]) .utf8_bytes(values[[index]]) else raw()
          c(.pack_u64(length(bytes)), bytes)
        },
        .abort_category("decoded-integrity", "unsupported canonical logical type")
      )
  })
  unlist(parts, use.names = FALSE)
}

.canonical_component <- function(component) {
  name <- .utf8_bytes(component$name)
  kind_tag <- switch(
    component$kind,
    vector = 1L,
    sparse_matrix = 2L,
    dense_matrix = 3L,
    .abort_category("decoded-integrity", "unsupported canonical component kind")
  )
  type_tag <- switch(
    component$logical_type,
    float64 = 1L,
    int64 = 2L,
    string = 3L,
    bool = 4L,
    .abort_category("decoded-integrity", "unsupported canonical logical type")
  )
  rank <- if (identical(component$kind, "vector")) 1L else 2L
  common <- c(
    .pack_u32(length(name)),
    name,
    as.raw(c(kind_tag, type_tag, rank))
  )

  if (identical(component$kind, "vector")) {
    valid <- component$valid
    return(c(
      common,
      .pack_u64(length(component$values)),
      .bitmap(valid),
      .canonical_values(component, valid)
    ))
  }
  if (identical(component$kind, "dense_matrix")) {
    valid <- component$valid
    if (length(component$values) != component$rows * component$columns) {
      .abort_category("decoded-integrity", "dense dimensions and values disagree")
    }
    return(c(
      common,
      .pack_u64(component$rows),
      .pack_u64(component$columns),
      .bitmap(valid),
      .canonical_values(component, valid)
    ))
  }

  if (!identical(component$logical_type, "float64")) {
    .abort_category("decoded-integrity", "sparse matrices must contain float64")
  }
  offsets <- component$row_offsets
  indices <- component$column_indices
  values <- component$values
  if (length(offsets) != component$rows + 1L ||
      !length(offsets) || offsets[[1]] != 0 ||
      tail(offsets, 1L) != length(values) ||
      length(indices) != length(values) ||
      any(diff(offsets) < 0) ||
      any(indices < 0 | indices >= component$columns) ||
      any(is.infinite(values) | (!is.nan(values) & values == 0))) {
    .abort_category("decoded-integrity", "invalid canonical sparse matrix")
  }
  for (row in seq_len(component$rows)) {
    start <- offsets[[row]] + 1L
    end <- offsets[[row + 1L]]
    if (end >= start && any(diff(indices[start:end]) <= 0)) {
      .abort_category("decoded-integrity", "sparse indices must increase within rows")
    }
  }
  c(
    common,
    .pack_u64(component$rows),
    .pack_u64(component$columns),
    .pack_u64(length(values)),
    unlist(lapply(offsets, .pack_u64), use.names = FALSE),
    unlist(lapply(indices, .pack_u64), use.names = FALSE),
    unlist(
      lapply(values, function(value) .float_bytes(value, TRUE)),
      use.names = FALSE
    )
  )
}

.canonical_bytes <- function(components) {
  names <- vapply(components, `[[`, character(1), "name")
  if (any(!nzchar(names)) || anyDuplicated(names)) {
    .abort_category("decoded-integrity", "component names must be nonempty and unique")
  }
  c(
    charToRaw("DMCF"),
    .pack_u16(1L),
    .pack_u32(length(components)),
    unlist(lapply(components, .canonical_component), use.names = FALSE)
  )
}

.canonical_sha256 <- function(components) {
  .sha256_raw(.canonical_bytes(components))
}

.descriptor_value <- function(value) {
  if (.is_scalar_character(value)) {
    if (identical(value, "-zero")) return(-0)
    if (identical(value, "nan")) return(NaN)
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
