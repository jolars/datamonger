test_that("Windows release builds keep Cargo objects outside the install path", {
  config <- test_path("..", "..", "tools", "config.R")
  skip_if_not(file.exists(config), "Configuration is tested from the source tree.")
  config <- normalizePath(config, winslash = "/")
  package <- normalizePath(test_path("..", ".."), winslash = "/")
  build <- tempfile("datamonger-config-")
  dir.create(file.path(build, "src", "rust"), recursive = TRUE)
  file.copy(file.path(package, "src", c("Makevars.in", "Makevars.win.in")),
            file.path(build, "src"))
  file.create(file.path(build, "src", "rust", "vendor.tar.xz"))

  previous <- setwd(build)
  on.exit({
    setwd(previous)
    unlink(build, recursive = TRUE)
  }, add = TRUE)
  for (windows in c(FALSE, TRUE)) {
    for (debug in c(FALSE, TRUE)) {
      env <- new.env(parent = baseenv())
      env$.Platform <- .Platform
      env$.Platform$OS.type <- if (windows) "windows" else "unix"
      env$Sys.getenv <- function(x, unset = "", ...) {
        if (identical(x, "DEBUG")) return(if (debug) "1" else "")
        if (identical(x, "DM_R_CORE_PATH")) return("")
        Sys.getenv(x, unset = unset, ...)
      }
      env$Sys.setenv <- function(...) invisible(NULL)
      sys.source(config, envir = env)
      makevars <- readLines(if (windows) "src/Makevars.win" else "src/Makevars")
      expect_false(any(grepl("@[A-Z_]+@", makevars)))
      if (windows && !debug) {
        target <- sub("^TARGET_DIR = ", "", makevars[grepl("^TARGET_DIR = ", makevars)])
        expect_identical(
          dirname(target), normalizePath(dirname(tempdir()), winslash = "/")
        )
        expect_match(basename(target), "^dm-")
        expect_false(dir.exists(target))
        expect_true('$(SHLIB): rust_build' %in% makevars)
        expect_match(makevars[grepl("^PKG_LIBS = ", makevars)],
                     '^PKG_LIBS = "\\$\\(STATLIB\\)" ')
        expect_true('\trm -rf .cargo vendor "$(TARGET_DIR)"' %in% makevars)
      } else {
        expect_true("TARGET_DIR = rust/target" %in% makevars)
      }
    }
  }
})
