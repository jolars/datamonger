args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 7L)
pkgload::load_all(file.path(args[[1]], "packages/r"), quiet = TRUE)
source(args[[6]])
prepared <- read_source(args[[2]], args[[3]], args[[4]])
numeric_values <- cbind(prepared$X, y = prepared$y)
metadata <- data.frame(
  sample_id = prepared$sample_id, tumor_id = prepared$tumor_id,
  Treatment = prepared$Treatment, Day = prepared$Day, CellLine = prepared$CellLine,
  RTV = prepared$RTV, stringsAsFactors = FALSE
)
restored <- read.csv(
  args[[5]], check.names = FALSE,
  colClasses = c("character", "character", "character", "integer", "character",
                 "numeric", rep("numeric", ncol(numeric_values)))
)
stopifnot(
  identical(names(restored), c(names(metadata), colnames(numeric_values))),
  identical(restored[, seq_len(6L)], metadata),
  identical(unname(as.matrix(restored[, -seq_len(6L)])), unname(numeric_values))
)
metadata_types <- c("string", "string", "string", "int64", "string", "float64")
components <- c(
  lapply(seq_along(metadata), function(column) {
    list(
      name = names(metadata)[[column]], kind = "vector",
      logical_type = metadata_types[[column]], values = metadata[[column]],
      valid = rep(TRUE, 101L)
    )
  }),
  lapply(seq_len(ncol(numeric_values)), function(column) {
    list(
      name = colnames(numeric_values)[[column]], kind = "vector",
      logical_type = "float64", values = numeric_values[, column],
      valid = rep(TRUE, 101L)
    )
  })
)
# Hash source values directly to check CSV serialization and Python decoding.
stopifnot(identical(datamonger:::`.canonical_sha256`(components), args[[7]]))
message("Original source values, metadata, and R/Python canonical digests agree.")
