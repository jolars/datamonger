args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 5L)
pkgload::load_all(file.path(args[[1]], "packages/r"), quiet = TRUE)
source(args[[4]])
prepared <- read_source(args[[2]])
values <- cbind(prepared$X, y = prepared$y)
restored <- read.csv(
  args[[3]], check.names = FALSE,
  colClasses = c("character", rep("numeric", ncol(values)))
)
stopifnot(
  identical(names(restored), c("sample_id", colnames(values))),
  identical(restored$sample_id, prepared$sample_id),
  identical(unname(as.matrix(restored[, -1L])), unname(values))
)
components <- c(
  list(list(
    name = "sample_id", kind = "vector", logical_type = "string",
    values = prepared$sample_id, valid = rep(TRUE, nrow(values))
  )),
  lapply(seq_len(ncol(values)), function(column) {
    list(
      name = colnames(values)[[column]], kind = "vector", logical_type = "float64",
      values = values[, column], valid = rep(TRUE, nrow(values))
    )
  })
)
# Hash official source values directly to check serialization and Python decoding.
message("Comparing the official source canonical digest with the Python CSV decoder.")
stopifnot(identical(datamonger:::`.canonical_sha256`(components), args[[5]]))
message("Official source values, sample IDs, gene names, and canonical digests agree.")
