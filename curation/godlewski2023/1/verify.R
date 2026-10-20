args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 2L)
pkgload::load_all(file.path(args[[1]], "packages/r"), quiet = TRUE)
bundle <- args[[2]]
manifest <- jsonlite::fromJSON(file.path(bundle, "provenance.json"))
values <- read.csv(gzfile(file.path(bundle, "data.csv.gz")), check.names = FALSE)
stopifnot(identical(dim(values), c(235L, 140L)))
stopifnot(identical(values[[1]], seq_len(235L)), !anyNA(values))
types <- c("int64", "string", rep("float64", 138L))
options <- list(
  encoding = "utf-8", delimiter = ",", header = TRUE, quote = '"',
  escape = "double", row_order = "source", missing_values = list(),
  columns = lapply(seq_along(values), function(j) {
    list(name = names(values)[[j]], type = types[[j]])
  })
)
decoded <- datamonger:::`.decode_delimited`(
  file.path(bundle, "data.csv.gz"), options, compression = "gzip"
)
stopifnot(identical(
  datamonger:::`.canonical_sha256`(decoded$components),
  manifest$representation$verification$digest[[1]]
))
message("R and Python CSV decoders have identical canonical digests.")
