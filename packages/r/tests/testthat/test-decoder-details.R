test_that("delimited decoding has strict lexical and record grammars", {
  recipe <- conformance_recipe(1)
  recipe$columns <- list(list(name = "x", type = "float64"))
  bad_float <- c(" 1", "+1", "NaN", "1e999")
  for (value in bad_float) {
    path <- write_text(paste0("x\n", value, "\n"))
    expect_error(
      dm_internal(".decode_delimited")(path, recipe),
      class = "datamonger_decode",
      info = value
    )
  }

  recipe$columns <- list(list(name = "x", type = "string"))
  bad_records <- c("x\r1\r", "x\n\"a\nb\"\n", "x\nhe\"llo\n", "x\n\"a\"b\n")
  for (body in bad_records) {
    expect_error(
      dm_internal(".decode_delimited")(write_text(body), recipe),
      class = "datamonger_decode"
    )
  }

  invalid_utf8 <- as.raw(c(charToRaw("x\n"), 0xff, charToRaw("\n")))
  expect_error(
    dm_internal(".decode_delimited")(write_bytes(invalid_utf8), recipe),
    class = "datamonger_decode"
  )
})

test_that("decimal float conversion is correctly rounded instead of R-truncated", {
  parsed <- dm_internal(".parse_binary64")("-0.179743")

  expect_identical(sprintf("%a", parsed), "-0x1.701d19157abb9p-3")
  expect_identical(sprintf("%a", dm_internal(".parse_binary64")("-0")), "-0x0p+0")
})

test_that("delimited decoding supports CRLF, exact int64, and no final LF", {
  recipe <- conformance_recipe(1)
  recipe$columns <- list(list(name = "x", type = "int64"))
  path <- write_text(paste0(
    "x\r\n",
    "9223372036854775807\r\n",
    "-9223372036854775808"
  ))

  decoded <- dm_internal(".decode_delimited")(path, recipe)

  expect_s3_class(decoded$data$x, "datamonger_int64")
  expect_identical(
    unclass(decoded$data$x),
    c("9223372036854775807", "-9223372036854775808")
  )
  encoded <- dm_internal(".canonical_bytes")(decoded$components)
  expect_identical(
    tail(encoded, 16L),
    as.raw(c(rep(0xff, 7), 0x7f, rep(0x00, 7), 0x80))
  )
})

test_that("declared gzip and bzip2 compression are decoded strictly", {
  cases <- read_fixture_json("conformance", "cases.json")$cases
  csv <- fixture_path("conformance", cases[[1]]$input)
  svm <- fixture_path("conformance", cases[[3]]$input)

  for (compression in c("gzip", "bzip2")) {
    decoded_csv <- dm_internal(".decode_delimited")(
      compress_fixture(csv, compression),
      cases[[1]]$recipe,
      compression
    )
    decoded_svm <- dm_internal(".decode_libsvm")(
      compress_fixture(svm, compression),
      cases[[3]]$recipe,
      compression
    )
    expect_identical(
      dm_internal(".canonical_sha256")(decoded_csv$components),
      cases[[1]]$expected_sha256
    )
    expect_identical(
      dm_internal(".canonical_sha256")(decoded_svm$components),
      cases[[3]]$expected_sha256
    )

    truncated <- compress_fixture(csv, compression)
    bytes <- readBin(truncated, "raw", n = file.info(truncated)$size)
    writeBin(head(bytes, -1L), truncated)
    expect_error(
      dm_internal(".decode_delimited")(truncated, cases[[1]]$recipe, compression),
      class = "datamonger_decode"
    )
  }
})

test_that("LIBSVM rejects unsupported records and preserves sparse output", {
  recipe <- conformance_recipe(3)
  malformed <- c(
    "\n",
    "+1 1:0\n",
    "+1 1:1 1:2\n",
    "+1 2:1 1:2\n",
    "+1 5:1\n",
    "+1 01:1\n",
    "+1 qid:1 1:1\n",
    "+1 1:1 # comment\n",
    "+01 1:1\n",
    " +1 1:1\n"
  )
  for (body in malformed) {
    expect_error(
      dm_internal(".decode_libsvm")(write_text(body), recipe),
      class = "datamonger_decode",
      info = body
    )
  }

  decoded <- dm_internal(".decode_libsvm")(
    fixture_path("conformance", "artifacts", "small.libsvm"),
    recipe
  )
  expect_s4_class(decoded$data$features, "dgRMatrix")
  expect_equal(
    as.matrix(decoded$data$features),
    matrix(c(1.5, 0, 0, -2, 0, 3, 0, 0), nrow = 2, byrow = TRUE)
  )
  expect_identical(unclass(decoded$data$response), c("1", "-1"))
})

test_that("LIBSVM retains exact dimensions beyond the Matrix integer limit", {
  recipe <- conformance_recipe(3)
  recipe$feature_count <- 2147483648

  decoded <- dm_internal(".decode_libsvm")(write_bytes(raw()), recipe)

  expect_s3_class(decoded$data$features, "datamonger_csr_matrix")
  expect_identical(dim(decoded$data$features), c(0, 2147483648))
  expect_identical(decoded$components[[1]]$columns, 2147483648)
})

test_that("canonical sparse NaNs normalize while infinities and zeros fail", {
  sparse <- dm_internal(".sparse_component")(
    "x", 1, 1, c(0, 1), 0, NaN
  )
  expect_identical(
    tail(dm_internal(".canonical_bytes")(list(sparse)), 8L),
    as.raw(c(0, 0, 0, 0, 0, 0, 0xf8, 0x7f))
  )
  sparse$values <- 0
  expect_error(
    dm_internal(".canonical_bytes")(list(sparse)),
    class = "datamonger_decoded_integrity"
  )
  sparse$values <- Inf
  expect_error(
    dm_internal(".canonical_bytes")(list(sparse)),
    class = "datamonger_decoded_integrity"
  )
})
