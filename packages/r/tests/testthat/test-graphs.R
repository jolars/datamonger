test_that("graph and HIF fetches preserve topology and verify canonical digests", {
  cases <- read_fixture_json("conformance", "graphs.json")$cases
  for (case in cases) {
    cache_dir <- tempfile("datamonger-graphs-")
    on.exit(unlink(cache_dir, recursive = TRUE), add = TRUE)
    registry <- seed_decoder_case(case, cache_dir)
    ref <- paste0("conformance:", case$id, "@1")
    result <- fetch_data(ref, registry = registry, cache_dir = cache_dir,
                         offline = TRUE, return_info = TRUE)
    expect_identical(result$info$canonical_digest,
      case$manifest$representation$expect$verification[[1L]]$digest)
    expect_setequal(names(result$info$artifact_digests), names(case$artifact_paths))
    if (identical(case$id, "graph")) {
      expect_s3_class(result$data, "datamonger_graph_dataset")
      expect_identical(format(result$data$nodes$id), c("9007199254740993", "7"))
      expect_equal(nrow(result$data$edges), 2L)
    } else {
      expect_s3_class(result$data, "datamonger_hypergraph_dataset")
      expect_identical(result$data$nodes$id, c("isolate", "inferred"))
      expect_true(is.na(result$data$nodes$label[[2L]]))
      expect_identical(format(result$data$hyperedges$id), "9007199254740993")
    }
  }
})
