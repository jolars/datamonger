args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
source(args[[3]])
prepared <- read_source(args[[1]])
reference <- readRDS(args[[2]])
stopifnot(
  identical(dim(reference$X), c(120L, 18975L)),
  all(colnames(reference$X) %in% colnames(prepared$X)),
  ncol(prepared$X) - ncol(reference$X) == 10L
)
values <- prepared$X[, colnames(reference$X), drop = FALSE]
# Identify rows with several probes, then verify all values after that mapping.
mapping <- vapply(seq_len(nrow(reference$X)), function(row) {
  errors <- apply(abs(sweep(values[, 1:5], 2L, reference$X[row, 1:5])), 1L, max)
  candidates <- which(errors <= 0.000501)
  stopifnot(length(candidates) == 1L)
  candidates[[1]]
}, integer(1))
stopifnot(!anyDuplicated(mapping))
difference <- max(
  abs(values[mapping, ] - reference$X),
  abs(prepared$y[mapping] - reference$y)
)
stopifnot(difference <= 0.000501)
message(sprintf(
  "All 120 samples and 18,976 shared probes match Iowa up to rounding; max error %.12g.",
  difference
))
message("The full-precision filter retains 10 additional predictor probes.")
