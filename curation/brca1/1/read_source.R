read_source <- function(directory) {
  paths <- list.files(directory, pattern = "^TCGA-.*[.]txt$", full.names = TRUE)
  sample_ids <- sub("[.]txt$", "", basename(paths))
  stopifnot(length(paths) == 606L, !anyDuplicated(sample_ids))
  # TCGA sample types 01 and 06 identify primary and metastatic tumors.
  keep <- substring(sample_ids, 14L, 15L) %in% c("01", "06")
  paths <- paths[keep]
  sample_ids <- sample_ids[keep]
  ordering <- order(sample_ids, method = "radix")
  paths <- paths[ordering]
  sample_ids <- sample_ids[ordering]
  stopifnot(length(paths) == 536L)

  read_sample <- function(path) {
    header <- readLines(path, n = 2L, warn = FALSE)
    stopifnot(
      identical(header[[1]], paste(
        "Hybridization REF", sub("[.]txt$", "", basename(path)), sep = "\t"
      )),
      identical(header[[2]], paste(
        "Composite Element REF",
        "log2 lowess normalized (cy5/cy3) collapsed by gene symbol", sep = "\t"
      ))
    )
    read.delim(
      path, skip = 2L, header = FALSE, col.names = c("gene", "value"),
      colClasses = c("character", "numeric"), na.strings = "null",
      quote = "", comment.char = "", check.names = FALSE
    )
  }
  first <- read_sample(paths[[1]])
  stopifnot(nrow(first) == 17814L, !anyDuplicated(first$gene), all(nzchar(first$gene)))
  measurements <- matrix(NA_real_, nrow = nrow(first), ncol = length(paths))
  measurements[, 1L] <- first$value
  for (column in seq.int(2L, length(paths))) {
    current <- read_sample(paths[[column]])
    stopifnot(identical(current$gene, first$gene))
    measurements[, column] <- current$value
  }
  rownames(measurements) <- first$gene
  colnames(measurements) <- sample_ids
  complete <- complete.cases(measurements)
  stopifnot(sum(!complete) == 491L, complete[[match("BRCA1", first$gene)]])
  features <- first$gene[complete & first$gene != "BRCA1"]
  features <- sort(features, method = "radix")
  stopifnot(length(features) == 17322L, !any(c("y", "sample_id") %in% features))
  result <- list(
    X = t(measurements[features, , drop = FALSE]),
    y = as.numeric(measurements["BRCA1", ]),
    sample_id = sample_ids
  )
  stopifnot(all(is.finite(result$X)), all(is.finite(result$y)))
  result
}
