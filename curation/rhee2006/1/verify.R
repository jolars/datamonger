args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
pkgload::load_all(file.path(args[[1]], "packages/r"), quiet = TRUE)
source(file.path(args[[2]], "read_source.R"))
source <- read_source(file.path(args[[2]], "PI_DATA.txt"))
values <- cbind(source$X, y = source$y)
components <- lapply(seq_len(ncol(values)), function(j) {
  list(
    name = colnames(values)[[j]], kind = "vector", logical_type = "float64",
    values = values[, j], valid = rep(TRUE, nrow(values))
  )
})

# Construct the logical components before CSV serialization to check the conversion.
stopifnot(identical(datamonger:::`.canonical_sha256`(components), args[[3]]))
options <- list(
  encoding = "utf-8", delimiter = ",", header = TRUE, quote = '"',
  escape = "double", row_order = "source", missing_values = list(),
  columns = lapply(colnames(values), function(name) list(name = name, type = "float64"))
)
decoded <- datamonger:::`.decode_delimited`(file.path(args[[2]], "data.csv"), options)
stopifnot(identical(datamonger:::`.canonical_sha256`(decoded$components), args[[3]]))
message("Prepared source, R CSV decoder, and Python CSV decoder have identical canonical digests.")
