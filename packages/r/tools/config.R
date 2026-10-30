personal_rust <- path.expand("~/.cargo/bin")
if (dir.exists(personal_rust)) {
  Sys.setenv(PATH = paste(Sys.getenv("PATH"), personal_rust,
                         sep = .Platform$path.sep))
}
cargo <- Sys.getenv("DM_CORE_CARGO", unset = Sys.getenv("CARGO", unset = Sys.which("cargo")))
rustc <- Sys.getenv("DM_CORE_RUSTC", unset = Sys.getenv("RUSTC", unset = Sys.which("rustc")))
if (!nzchar(cargo) || !nzchar(rustc)) {
  stop("Datamonger requires Cargo and rustc >= 1.82. Install the Rust toolchain.")
}
rust_version <- system2(rustc, "--version", stdout = TRUE)
cargo_version <- system2(cargo, "--version", stdout = TRUE)
package_manager <- sub("^cargo ([0-9.]+).*", "\\1", cargo_version)
if (utils::compareVersion(package_manager, "1.82.0") < 0) {
  stop("Datamonger requires Cargo >= 1.82.0; found ", package_manager)
}
version <- sub("^rustc ([0-9.]+).*", "\\1", rust_version)
if (utils::compareVersion(version, "1.82.0") < 0) {
  stop("Datamonger requires rustc >= 1.82.0; found ", version)
}
message(rust_version, "\n", cargo_version)
debug <- nzchar(Sys.getenv("DEBUG"))
core <- Sys.getenv("DM_R_CORE_PATH")
local_core <- nzchar(core)
patch <- ""
if (local_core) {
  core <- normalizePath(core, winslash = "/", mustWork = TRUE)
  if (!file.exists(file.path(core, "Cargo.toml"))) {
    stop("DM_R_CORE_PATH must point to the datamonger-core crate.")
  }
  patch <- paste("--config", shQuote(paste0(
    "patch.crates-io.datamonger-core.path=", encodeString(core, quote = '"')
  )))
  unlink("src/.cargo/config.toml")
}
vendored <- !local_core && file.exists("src/rust/vendor.tar.xz")
if (!vendored && !local_core && !nzchar(Sys.getenv("NOT_CRAN"))) {
  stop("Missing vendored Rust sources. Run devenv tasks run r:vendor before building.")
}
windows <- .Platform$OS.type == "windows"
target_dir <- "rust/target"
if (windows && !debug) {
  # MinGW cannot link the document helper when object paths exceed MAX_PATH.
  # Use the session's parent so this directory survives configure's Rscript.
  target_dir <- tempfile("dm-", tmpdir = normalizePath(
    dirname(tempdir()), winslash = "/", mustWork = TRUE
  ))
}
template <- if (windows) "src/Makevars.win.in" else "src/Makevars.in"
text <- readLines(template)
replacements <- list(
  "@CARGO@" = shQuote(cargo),
  "@RUSTC@" = shQuote(rustc),
  "@CORE_PATCH@" = patch,
  "@LOCKED@" = if (local_core) "" else "--locked",
  "@VENDORED@" = if (vendored) "true" else "false",
  "@CARGO_HOME@" = if (local_core) "" else 'CARGO_HOME="$(CURDIR)/.cargo"',
  "@NATIVE_LIBS@" = if (grepl("darwin", R.version$os)) "" else "-ldl -lpthread -lm",
  "@PROFILE@" = if (debug) "" else "--release",
  "@LIBDIR@" = if (debug) "debug" else "release",
  "@TARGET_DIR@" = target_dir,
  "@OFFLINE@" = if (vendored) "--offline" else "",
  "@CLEAN_TARGET@" = if (debug) "" else '"$(TARGET_DIR)"'
)
for (key in names(replacements)) {
  text <- gsub(key, replacements[[key]], text, fixed = TRUE)
}
writeLines(text, sub("\\.in$", "", template))
