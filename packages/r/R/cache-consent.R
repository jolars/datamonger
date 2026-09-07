#' Select the R client's private cache directory
#'
#' Datamonger writes to the platform user cache only after explicit consent.
#' Set `options(datamonger.cache_consent = TRUE)` to allow persistent caching,
#' or set it to `FALSE` to use a session-temporary cache. In an interactive
#' session, an unset option causes one prompt, whose answer is remembered only
#' for that session. An explicit `cache_dir` always takes precedence.
#'
#' @param cache_dir An explicit cache directory, or `NULL` to apply the consent
#'   policy.
#' @param .interactive Whether the current session is interactive. This testing
#'   seam should normally be left at its default.
#' @param .ask Function used for an interactive yes-or-no question.
#' @return A path. Merely selecting it does not create the directory.
#' @export
datamonger_cache_dir <- function(
    cache_dir = NULL,
    .interactive = interactive(),
    .ask = utils::askYesNo) {
  if (!is.null(cache_dir)) {
    return(path.expand(cache_dir))
  }

  consent <- getOption("datamonger.cache_consent")
  if (!is.null(consent) && !.is_scalar_logical(consent)) {
    .abort_category(
      "cache",
      "option 'datamonger.cache_consent' must be TRUE, FALSE, or unset"
    )
  }
  if (is.null(consent) && isTRUE(.interactive)) {
    consent <- isTRUE(.ask(paste(
      "May Datamonger keep verified datasets in your persistent user cache?",
      "Choose No to use only this R session's temporary directory."
    )))
    options(datamonger.cache_consent = consent)
  }
  if (isTRUE(consent)) {
    return(file.path(tools::R_user_dir("datamonger", "cache"), "r"))
  }
  file.path(tempdir(), "datamonger", "r")
}
