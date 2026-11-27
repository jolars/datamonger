# Extract the six-subtype cohort from the pinned stjudem data object.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
source_data <- new.env(parent = emptyenv())
stopifnot(identical(load(args[[1]], envir = source_data), "stjude"))
stjude <- source_data$stjude
stopifnot(
  identical(dim(stjude$expr), c(12625L, 327L)),
  identical(stjude$chip, "hgu95av2"),
  length(stjude$labels) == ncol(stjude$expr),
  !anyNA(stjude$labels),
  all(is.finite(stjude$expr))
)

counts <- c(BCR = 15L, E2A = 27L, Hyperdip = 64L, MLL = 20L, T = 43L, TEL = 79L)
selected <- stjude$labels %in% names(counts)
labels <- stjude$labels[selected]
stopifnot(identical(as.integer(table(factor(labels, levels = names(counts)))), unname(counts)))

expr <- stjude$expr[, selected, drop = FALSE]
probes <- rownames(expr)
samples <- colnames(expr)
header <- c("sample_id", probes, "subtype")
stopifnot(
  length(probes) == nrow(expr),
  length(samples) == ncol(expr),
  !anyDuplicated(header),
  !anyDuplicated(samples),
  all(nzchar(header)),
  all(nzchar(samples)),
  !any(grepl("[\r\n]", c(header, samples, labels)))
)

quote_csv <- function(x) paste0('"', gsub('"', '""', x, fixed = TRUE), '"')
con <- file(args[[2]], open = "wb")
writeLines(paste(quote_csv(header), collapse = ","), con)
for (i in seq_along(samples)) {
  row <- c(quote_csv(samples[[i]]), sprintf("%.17g", expr[, i]), quote_csv(labels[[i]]))
  writeLines(paste(row, collapse = ","), con)
}
close(con)

# Write source bits in sample order for comparison with the decoded CSV.
writeBin(as.vector(expr), args[[3]], size = 8L, endian = "little")
