read_source <- function(path) {
  lines <- readLines(gzfile(path), warn = FALSE)
  start <- match("!series_matrix_table_begin", lines)
  end <- match("!series_matrix_table_end", lines)
  stopifnot(!is.na(start), !is.na(end), start < end)
  values <- read.delim(
    textConnection(lines[seq.int(start + 1L, end - 1L)]),
    row.names = 1L, check.names = FALSE, colClasses = c("character", rep("numeric", 120L))
  )
  values <- as.matrix(values)
  stopifnot(
    identical(dim(values), c(31099L, 120L)),
    !anyDuplicated(rownames(values)), !anyDuplicated(colnames(values)),
    all(is.finite(values)), all(grepl("^GSM[0-9]+$", colnames(values)))
  )
  controls <- grepl("^AFFX", rownames(values))
  stopifnot(sum(controls) == 57L)
  values <- values[!controls, , drop = FALSE]
  threshold <- unname(quantile(values, 0.25, type = 7L))
  # A twofold change is one unit on the submitted RMA log2 scale.
  keep <- apply(values, 1L, max) > threshold &
    apply(values, 1L, function(probe) diff(range(probe))) >= 1
  target <- "1389163_at"
  stopifnot(keep[[match(target, rownames(values))]])
  features <- rownames(values)[keep & rownames(values) != target]
  stopifnot(length(features) == 18985L)
  list(
    X = t(values[features, , drop = FALSE]),
    y = as.numeric(values[target, ]),
    sample_id = colnames(values),
    threshold = threshold
  )
}
