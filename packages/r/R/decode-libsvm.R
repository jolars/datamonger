.validate_libsvm_options <- function(options) {
  .require_exact_fields(
    options,
    c(
      "index_base",
      "feature_count",
      "duplicate_features",
      "label_type",
      "row_order",
      "target_name"
    ),
    "LIBSVM options",
    "datamonger_unsupported_decoder"
  )
  if (!identical(options$index_base, 1L) ||
      !identical(options$duplicate_features, "error") ||
      !.is_scalar_character(options$label_type) ||
      !(options$label_type %in% c("int64", "float64")) ||
      !identical(options$row_order, "source") ||
      !.is_scalar_character(options$target_name) ||
      !nzchar(options$target_name) ||
      identical(options$target_name, "features") ||
      !.is_exact_number(options$feature_count, minimum = 1)) {
    .abort_category("unsupported-decoder", "unsupported LIBSVM recipe")
  }
  options
}

.parse_libsvm_float <- function(value, description) {
  if (!grepl(.float_pattern, value, perl = TRUE)) {
    .abort_category("decode", paste0("invalid ", description))
  }
  parsed <- .parse_binary64(value)
  if (is.null(parsed)) {
    .abort_category("decode", paste0("non-finite ", description))
  }
  parsed
}

.decode_libsvm <- function(path, options, compression = "none") {
  options <- .validate_libsvm_options(options)
  records <- .strict_records(.decompress_artifact(path, compression), allow_empty = TRUE)
  if (any(!nzchar(records)) || any(grepl("^[ \t]", records))) {
    .abort_category("decode", "LIBSVM records must be nonblank without leading whitespace")
  }

  row_offsets <- numeric(length(records) + 1L)
  row_indices <- vector("list", length(records))
  row_values <- vector("list", length(records))
  labels <- if (identical(options$label_type, "int64")) {
    character(length(records))
  } else {
    numeric(length(records))
  }

  for (row_index in seq_along(records)) {
    record <- sub("[ \t]+$", "", records[[row_index]], perl = TRUE)
    fields <- strsplit(record, "[ \t]+", perl = TRUE)[[1]]
    label <- fields[[1]]
    if (identical(options$label_type, "int64")) {
      parsed_label <- .normalize_int64(label, allow_plus = TRUE)
      if (is.null(parsed_label)) {
        .abort_category("decode", paste0("invalid int64 label at row ", row_index))
      }
      labels[[row_index]] <- parsed_label
    } else {
      labels[[row_index]] <- .parse_libsvm_float(
        label,
        paste0("label at row ", row_index)
      )
    }

    previous <- 0
    indices <- numeric(max(length(fields) - 1L, 0L))
    values <- numeric(max(length(fields) - 1L, 0L))
    if (length(fields) > 1L) {
      for (field_index in seq_along(fields[-1L])) {
        field <- fields[-1L][[field_index]]
        parts <- strsplit(field, ":", fixed = TRUE)[[1]]
        if (length(parts) != 2L || !grepl("^(0|[1-9][0-9]*)$", parts[[1]])) {
          .abort_category("decode", paste0("invalid feature at row ", row_index))
        }
        index <- suppressWarnings(as.numeric(parts[[1]]))
        if (!is.finite(index) || index < 1 || index > options$feature_count ||
            index <= previous) {
          .abort_category(
            "decode",
            paste0("feature indices are invalid or unordered at row ", row_index)
          )
        }
        value <- .parse_libsvm_float(
          parts[[2]],
          paste0("feature value at row ", row_index)
        )
        if (value == 0) {
          .abort_category("decode", paste0("stored sparse zero at row ", row_index))
        }
        indices[[field_index]] <- index - 1
        values[[field_index]] <- value
        previous <- index
      }
    }
    row_indices[[row_index]] <- indices
    row_values[[row_index]] <- values
    row_offsets[[row_index + 1L]] <- row_offsets[[row_index]] + length(values)
  }
  column_indices <- unlist(row_indices, use.names = FALSE)
  feature_values <- unlist(row_values, use.names = FALSE)

  matrix <- .native_sparse_matrix(
    length(records),
    options$feature_count,
    row_offsets,
    column_indices,
    feature_values
  )
  response <- if (identical(options$label_type, "int64")) {
    .new_int64(labels)
  } else {
    labels
  }
  components <- list(
    .sparse_component(
      "features",
      length(records),
      options$feature_count,
      row_offsets,
      column_indices,
      feature_values
    ),
    .vector_component(
      options$target_name,
      options$label_type,
      labels,
      rep(TRUE, length(records))
    )
  )
  data <- structure(
    list(features = matrix, response = response),
    class = "datamonger_sparse_dataset"
  )
  list(data = data, components = components)
}

.rename_sparse_components <- function(decoded, prefix, target_name) {
  decoded$components[[1]]$name <- paste0(prefix, "_features")
  decoded$components[[2]]$name <- paste0(prefix, "_", target_name)
  decoded
}

.decode_libsvm_split <- function(
    train_path,
    test_path,
    options,
    train_compression = "none",
    test_compression = "none") {
  train <- .rename_sparse_components(
    .decode_libsvm(train_path, options, train_compression),
    "train",
    options$target_name
  )
  test <- .rename_sparse_components(
    .decode_libsvm(test_path, options, test_compression),
    "test",
    options$target_name
  )
  list(
    data = structure(
      list(train = train$data, test = test$data),
      class = "datamonger_sparse_dataset_split"
    ),
    components = c(train$components, test$components)
  )
}
