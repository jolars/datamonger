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
vendored <- file.exists("src/rust/vendor.tar.xz")
if (!vendored && !nzchar(Sys.getenv("NOT_CRAN"))) {
  stop("Missing vendored Rust sources. Run dm-vendor-r before building.")
}
template <- if (.Platform$OS.type == "windows") "src/Makevars.win.in" else "src/Makevars.in"
text <- readLines(template)
replacements <- list(
  "@CARGO@" = shQuote(cargo),
  "@RUSTC@" = shQuote(rustc),
  "@NATIVE_LIBS@" = if (grepl("darwin", R.version$os)) "" else "-ldl -lpthread -lm",
  "@PROFILE@" = if (debug) "" else "--release",
  "@LIBDIR@" = if (debug) "debug" else "release",
  "@OFFLINE@" = if (vendored) "--offline" else "",
  "@CLEAN_TARGET@" = if (debug) "" else "$(TARGET_DIR)"
)
for (key in names(replacements)) {
  text <- gsub(key, replacements[[key]], text, fixed = TRUE)
}
writeLines(text, sub("\\.in$", "", template))
