args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 5L)
options(OutDec = ".")
invisible(Sys.setlocale("LC_NUMERIC", "C"))
source(args[[5]])
prepared <- read_source(args[[1]], args[[2]], args[[3]])
values <- cbind(prepared$X, y = prepared$y)
metadata_names <- c("sample_id", "tumor_id", "Treatment", "Day", "CellLine", "RTV")
stopifnot(!any(colnames(values) %in% metadata_names), !anyDuplicated(colnames(values)))
quote_field <- function(value) paste0('"', gsub('"', '""', value, fixed = TRUE), '"')
connection <- file(args[[4]], open = "wt", encoding = "UTF-8")
writeLines(paste(quote_field(c(metadata_names, colnames(values))), collapse = ","), connection)
# Seventeen significant digits preserve the averaged binary64 values and log2 response.
for (row in seq_len(nrow(values))) {
  fields <- c(
    quote_field(prepared$sample_id[[row]]), quote_field(prepared$tumor_id[[row]]),
    quote_field(prepared$Treatment[[row]]), as.character(prepared$Day[[row]]),
    quote_field(prepared$CellLine[[row]]), sprintf("%.17g", prepared$RTV[[row]]),
    sprintf("%.17g", values[row, ])
  )
  writeLines(paste(fields, collapse = ","), connection)
}
close(connection)
