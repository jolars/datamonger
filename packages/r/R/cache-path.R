#' Select the R client's private cache directory
#'
#' Datamonger uses the platform user cache by default. An explicit `cache_dir`
#' always takes precedence and can select temporary storage when persistence is
#' undesirable.
#'
#' @param cache_dir An explicit cache directory, or `NULL` for the platform
#'   default.
#' @return A path. Merely selecting it does not create the directory.
#' @export
datamonger_cache_dir <- function(cache_dir = NULL) {
  if (!is.null(cache_dir)) {
    return(path.expand(cache_dir))
  }

  file.path(tools::R_user_dir("datamonger", "cache"), "r")
}
