args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 5L)
source(args[[5]])
prepared <- read_source(args[[1]], args[[2]], args[[3]])
reference <- readRDS(args[[4]])
stopifnot(
  identical(dim(reference$X), c(101L, 34694L)),
  setequal(colnames(prepared$X), colnames(reference$X)),
  identical(rownames(reference$X), prepared$tumor_id)
)
values <- prepared$X[, colnames(reference$X), drop = FALSE]
difference <- max(abs(values - reference$X))
response_difference <- max(abs(as.numeric(reference$y) - prepared$y))
stopifnot(
  difference <= 1e-12,
  response_difference <= 1e-14,
  identical(as.character(reference$sData$Treatment), prepared$Treatment),
  identical(as.integer(reference$sData$Day), prepared$Day)
)
message(sprintf(
  "All 101 samples and 34,694 predictors match Iowa; max absolute error %.12g.",
  difference
))
message(sprintf("The log2 response agrees within %.12g; treatment and day match exactly.",
                response_difference))
