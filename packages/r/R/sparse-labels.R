.sparse_label_setup <- function(dataset, representation) {
  fail <- function(message) .abort_category("unsupported-decoder", message)
  if (!identical(dataset$schema_version, 9L) ||
      !identical(dataset$modality, "tabular") ||
      !identical(representation$decoder_version, 1L)) {
    fail("sparse label joins require manifest schema 9 and decoder version 1")
  }
  if (!dm_supports_sparse_label_join()) {
    fail("sparse label joins require an updated native core")
  }
  options <- representation$options
  fields <- c("train", "test", "feature_count", "label_count")
  if (!is.list(options) || !setequal(names(options), fields)) {
    fail("invalid sparse label join options")
  }
  count <- function(value) {
    is.numeric(value) && length(value) == 1L && is.finite(value) &&
      value == trunc(value) && value >= 1 && value < 2^53
  }
  if (!count(options$feature_count) || !count(options$label_count)) {
    fail("invalid sparse label join dimensions")
  }
  roles <- "labels"
  for (split in c("train", "test")) {
    shards <- options[[split]]
    if (!is.list(shards) || !is.null(names(shards)) || length(shards) == 0L ||
        !all(vapply(shards, function(role) {
          .is_scalar_character(role) && nzchar(role)
        }, logical(1)))) {
      fail("each split requires ordered input roles")
    }
    roles <- c(roles, unlist(shards, use.names = FALSE))
  }
  if (anyDuplicated(roles)) {
    fail("sparse label join roles must be distinct")
  }
  artifacts <- .representation_artifacts(dataset, representation, roles)
  names <- vapply(artifacts, `[[`, character(1), "name")
  formats <- vapply(artifacts, `[[`, character(1), "format")
  compressions <- vapply(artifacts, `[[`, character(1), "compression")
  if (anyDuplicated(names) ||
      !identical(formats, c("label-assignments", rep("id-sparse", length(roles) - 1L))) ||
      !all(compressions %in% c("none", "gzip", "bzip2"))) {
    fail("invalid sparse label join artifacts")
  }
  list(
    representation = representation,
    decoder = "sparse-label-join",
    options = list(
      feature_count = options$feature_count,
      label_count = options$label_count,
      train_shards = length(options$train)
    ),
    artifacts = artifacts,
    compressions = compressions
  )
}

.decode_sparse_labels <- function(setup, paths, hash) {
  decoded <- .native_result(dm_decode(
    setup$decoder, paths, setup$compressions, setup$options, hash
  ))
  components <- decoded$components
  matrix <- function(component) {
    .native_sparse_matrix(
      component$rows,
      component$columns,
      component$row_offsets,
      component$column_indices,
      component$values
    )
  }
  split <- function(start) {
    structure(
      list(
        features = matrix(components[[start]]),
        response = matrix(components[[start + 1L]]),
        label_index_base = 0L,
        document_id = components[[start + 2L]]$values,
        label_codes = components[[7L]]$values
      ),
      class = "datamonger_multilabel_sparse_dataset"
    )
  }
  decoded$data <- structure(
    list(train = split(1L), test = split(4L)),
    class = c("datamonger_dataset_splits", "list")
  )
  decoded
}
