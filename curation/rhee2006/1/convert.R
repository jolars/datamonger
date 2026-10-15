args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L)
options(OutDec = ".")
invisible(Sys.setlocale("LC_NUMERIC", "C"))
source(args[[3]])
source <- read_source(args[[1]])
stopifnot(
  identical(names(source), c("X", "y")),
  is.matrix(source$X), is.double(source$X),
  identical(dim(source$X), c(842L, 361L)),
  is.double(source$y), length(source$y) == nrow(source$X),
  all(is.finite(source$X)), all(is.finite(source$y)),
  all(source$X %in% c(0, 1)),
  !is.null(colnames(source$X)), !anyDuplicated(colnames(source$X)),
  !"y" %in% colnames(source$X)
)

# Seventeen significant digits preserve every binary64 value on reimport.
values <- cbind(source$X, y = source$y)
header <- paste0('"', gsub('"', '""', colnames(values), fixed = TRUE), '"')
records <- apply(values, 1L, function(row) paste(sprintf("%.17g", row), collapse = ","))
writeLines(c(paste(header, collapse = ","), records), args[[2]], useBytes = TRUE)

# Verify the complete round trip independently of the Python decoder.
restored <- read.csv(args[[2]], check.names = FALSE, colClasses = "numeric")
stopifnot(
  identical(names(restored), colnames(values)),
  identical(unname(as.matrix(restored)), unname(values))
)
