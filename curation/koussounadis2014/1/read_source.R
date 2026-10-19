read_source <- function(matrix_path, platform_path, phenodata_path) {
  lines <- readLines(gzfile(matrix_path), warn = FALSE)
  start <- match("!series_matrix_table_begin", lines)
  end <- match("!series_matrix_table_end", lines)
  stopifnot(!is.na(start), !is.na(end), start < end)
  expression <- as.matrix(read.delim(
    textConnection(lines[seq.int(start + 1L, end - 1L)]),
    row.names = 1L, check.names = FALSE,
    colClasses = c("character", rep("numeric", 101L))
  ))
  metadata <- function(prefix) {
    records <- lines[startsWith(lines, prefix)]
    stopifnot(length(records) == 1L)
    fields <- scan(text = records, what = character(), sep = "\t", quiet = TRUE)
    stopifnot(length(fields) == 102L)
    fields[-1L]
  }
  samples <- metadata("!Sample_geo_accession\t")
  descriptions <- metadata("!Sample_description\t")
  stopifnot(all(startsWith(descriptions, "Sample name: ")))
  tumors <- sub("^Sample name: ", "", descriptions)
  stopifnot(
    identical(dim(expression), c(47323L, 101L)),
    identical(colnames(expression), samples),
    !anyDuplicated(rownames(expression)), !anyDuplicated(samples),
    !anyDuplicated(tumors), all(is.finite(expression))
  )

  platform_lines <- readLines(platform_path, warn = FALSE)
  start <- match("!platform_table_begin", platform_lines)
  end <- match("!platform_table_end", platform_lines)
  stopifnot(!is.na(start), !is.na(end), start < end)
  platform <- read.delim(
    textConnection(platform_lines[seq.int(start + 1L, end - 1L)]),
    check.names = FALSE, colClasses = "character", quote = "", comment.char = "",
    na.strings = character()
  )
  stopifnot(!anyDuplicated(platform$ID))
  annotation <- match(rownames(expression), platform$ID)
  stopifnot(!anyNA(annotation))
  genes <- platform$ILMN_Gene[annotation]
  stopifnot(all(nzchar(genes)), !anyNA(genes))
  # Pin the ordering because factor levels otherwise depend on the user's locale.
  groups <- factor(genes, levels = sort(unique(genes), method = "radix"))
  predictors <- t(vapply(seq_len(ncol(expression)), function(column) {
    as.numeric(tapply(expression[, column], groups, mean))
  }, numeric(nlevels(groups))))
  colnames(predictors) <- levels(groups)
  rownames(predictors) <- tumors
  stopifnot(identical(dim(predictors), c(101L, 34694L)))

  phenodata <- read.delim(
    gzfile(phenodata_path), row.names = 1L, check.names = FALSE,
    colClasses = c("character", "character", "character", "integer", "character", "numeric")
  )
  stopifnot(
    nrow(phenodata) == 101L, !anyDuplicated(phenodata$ID),
    setequal(phenodata$ID, tumors)
  )
  phenodata <- phenodata[match(tumors, phenodata$ID), , drop = FALSE]
  expected <- paste(phenodata$CellLine, phenodata$Treatment, paste0("Day", phenodata$Day))
  stopifnot(
    identical(metadata("!Sample_source_name_ch1\t"), expected),
    all(phenodata$Treatment %in% c("Carbo", "CarboTax", "Control")),
    all(phenodata$CellLine %in% c("OV1002", "HOX424")),
    all(phenodata$Day %in% c(0L, 1L, 2L, 4L, 7L, 14L)),
    all(is.finite(phenodata$RTV)), all(phenodata$RTV > 0),
    all(phenodata$RTV[phenodata$Day == 0L] == 1)
  )
  list(
    X = predictors, y = log2(phenodata$RTV), sample_id = samples,
    tumor_id = tumors, Treatment = phenodata$Treatment, Day = phenodata$Day,
    CellLine = phenodata$CellLine, RTV = phenodata$RTV,
    probe_count = nrow(expression), grouped_probes = table(groups)
  )
}
