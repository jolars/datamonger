.split_component_name <- function(split, component) {
  escape <- function(value) {
    gsub("/", "~1", gsub("~", "~0", value, fixed = TRUE), fixed = TRUE)
  }
  paste0(escape(split), "/", escape(component))
}

.split_recipes <- function(representation) {
  fail <- function(message) .abort_category("unsupported-decoder", message)
  if (!identical(representation$decoder_version, 1L)) {
    fail("unsupported named-splits version")
  }
  options <- representation$options
  if (!is.list(options) || !setequal(names(options), "splits")) {
    fail("named-splits options must contain exactly splits")
  }
  splits <- options$splits
  if (!is.list(splits) || length(splits) == 0L || !is.null(names(splits))) {
    fail("splits must be a nonempty array")
  }
  split_names <- character()
  for (split in splits) {
    fields <- c("name", "decoder", "decoder_version", "options")
    if (!is.list(split) || !setequal(names(split), fields)) {
      fail("invalid split recipe fields")
    }
    if (
      !.is_scalar_character(split$name) ||
        !nzchar(split$name) ||
        split$name %in% split_names
    ) {
      fail("split names must be nonempty and unique")
    }
    split_names <- c(split_names, split$name)
    if (
      !(identical(split$decoder_version, 1L) ||
        (identical(split$decoder_version, 2L) &&
          identical(split$decoder, "libsvm"))) ||
        !.is_scalar_character(split$decoder) ||
        !(split$decoder %in% c("delimited-text", "libsvm")) ||
        !is.list(split$options)
    ) {
      fail("unsupported split decoder recipe")
    }
  }
  if (
    !is.list(representation$inputs) ||
      !setequal(names(representation$inputs), split_names)
  ) {
    fail("input names must match the declared split names")
  }
  splits
}

.decode_setup <- function(setup, paths, hash) {
  if (identical(setup$decoder, "named-splits")) {
    data <- list()
    components <- list()
    for (i in seq_along(setup$children)) {
      child <- .decode_setup(setup$children[[i]], paths[i], FALSE)
      name <- setup$options$splits[[i]]$name
      data[[name]] <- child$data
      for (component in child$components) {
        component$name <- .split_component_name(name, component$name)
        components[[length(components) + 1L]] <- component
      }
    }
    return(list(
      data = structure(data, class = c("datamonger_dataset_splits", "list")),
      components = components,
      canonical_digest = if (hash) .canonical_sha256(components) else NULL
    ))
  }
  switch(
    setup$decoder,
    `delimited-text` = .decode_delimited(
      paths[[1]],
      setup$options,
      setup$compressions[[1]],
      hash = hash
    ),
    libsvm = .decode_libsvm(
      paths[[1]],
      setup$options,
      setup$compressions[[1]],
      hash = hash,
      decoder_version = setup$representation$decoder_version
    ),
    `libsvm-split` = .decode_libsvm_split(
      paths[[1]],
      paths[[2]],
      setup$options,
      setup$compressions[[1]],
      setup$compressions[[2]],
      hash = hash,
      decoder_version = setup$representation$decoder_version
    )
  )
}
