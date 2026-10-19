pkgload::load_all(".", helpers = FALSE)
wrappers <- .Call(
  "wrap__make_datamonger_wrappers", TRUE, "datamonger", PACKAGE = "datamonger"
)
writeLines(c("# Generated from extendr metadata. Do not edit.", wrappers),
           "R/extendr-wrappers.R")
