read_source <- function(path) {
  gene <- read.delim(path, na.strings = c("NA", ""), stringsAsFactors = FALSE)
  start <- which(names(gene) == "P1")
  stopifnot(length(start) == 1L, identical(tail(names(gene), 1L), "P99"))
  positions <- start:ncol(gene)
  valid <- apply(gene[, positions], 1L, function(row) {
    all(grepl("^(\\.|-|[A-Zid]+)$", row))
  })
  gene <- gene[valid, ]

  # Match Iowa's mutation-major column order and treatment of mixed residues.
  X <- do.call(cbind, lapply(c(LETTERS, "i", "d"), function(mutation) {
    block <- sapply(gene[, positions], function(column) {
      as.numeric(grepl(mutation, column, fixed = TRUE))
    })
    colnames(block) <- paste(names(gene)[positions], mutation, sep = ".")
    block
  }))
  # Iowa removes globally absent mutations before selecting observed NFV outcomes.
  X <- X[, colSums(X) != 0]
  y <- log(gene$NFV)
  observed <- !is.na(y)
  list(X = X[observed, ], y = y[observed])
}
