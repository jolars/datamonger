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

  if (
    !identical(options$index_base, 1L) ||
      !identical(options$duplicate_features, "error") ||
      !.is_scalar_character(options$label_type) ||
      !(options$label_type %in% c("int64", "float64")) ||
      !identical(options$row_order, "source") ||
      !.is_scalar_character(options$target_name) ||
      !nzchar(options$target_name) ||
      identical(options$target_name, "features") ||
      !.is_exact_number(options$feature_count, minimum = 1)
  ) {
    .abort_category("unsupported-decoder", "unsupported LIBSVM recipe")
  }

  options
}

.sparse_data <- function(components) {
  features <- components[[1]]
  structure(
    list(
      features = .native_sparse_matrix(
        features$rows, features$columns, features$row_offsets,
        features$column_indices, features$values
      ),
      response = .public_vector(components[[2]])
    ),
    class = "datamonger_sparse_dataset"
  )
}

.decode_libsvm <- function(path, options, compression = "none", hash = FALSE) {
  options <- .validate_libsvm_options(options)
  decoded <- .native_result(dm_decode("libsvm", path, compression, options, hash))
  decoded$data <- .sparse_data(decoded$components)
  decoded
}

.decode_libsvm_split <- function(
  train_path, test_path, options,
  train_compression = "none", test_compression = "none", hash = FALSE
) {
  options <- .validate_libsvm_options(options)
  decoded <- .native_result(dm_decode(
    "libsvm-split", c(train_path, test_path),
    c(train_compression, test_compression), options, hash
  ))
  decoded$data <- structure(
    list(
      train = .sparse_data(decoded$components[1:2]),
      test = .sparse_data(decoded$components[3:4])
    ),
    class = "datamonger_sparse_dataset_split"
  )
  decoded
}
