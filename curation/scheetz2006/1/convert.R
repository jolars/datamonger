args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
options(OutDec = ".")
invisible(Sys.setlocale("LC_NUMERIC", "C"))
source(args[[3]])
prepared <- read_source(args[[1]])
values <- cbind(prepared$X, y = prepared$y)
names <- c("sample_id", colnames(values))
header <- paste0('"', gsub('"', '""', names, fixed = TRUE), '"')
connection <- file(args[[2]], open = "wt", encoding = "UTF-8")
writeLines(paste(header, collapse = ","), connection, useBytes = TRUE)
# Seventeen significant digits preserve the submitted binary64 measurements.
for (row in seq_len(nrow(values))) {
  fields <- c(paste0('"', prepared$sample_id[[row]], '"'), sprintf("%.17g", values[row, ]))
  writeLines(paste(fields, collapse = ","), connection)
}
close(connection)
