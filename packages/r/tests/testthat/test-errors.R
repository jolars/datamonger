test_that("shared semantic categories map to distinct R condition classes", {
  cases <- read_fixture_json("conformance", "errors.json")$cases
  classes <- vapply(
    cases,
    function(case) dm_internal(".condition_class")(case$expected),
    character(1)
  )

  expect_setequal(
    vapply(cases, `[[`, character(1), "expected"),
    names(dm_internal(".error_classes"))
  )
  expect_length(unique(classes), length(classes))
  expect_true(all(startsWith(classes, "datamonger_")))
})
