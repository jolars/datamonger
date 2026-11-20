#' Select and Manage the Private R Cache
#'
#' Datamonger uses the cache returned by `tools::R_user_dir()` by default. An
#' explicit path can select another persistent or temporary location. Eviction
#' is manual, and active objects are skipped.
#'
#' @param cache_dir An explicit cache path, or `NULL` for the platform default.
#' @param dataset A canonical `source:name@version` filter.
#' @param older_than A nonnegative `difftime` or number of seconds.
#'
#' @returns
#' `datamonger_cache_dir()` returns a path without creating it. `cache_info()`
#' returns a cache inventory. `cache_clean()` reports removed and skipped
#' objects and the number of bytes removed.
#'
#' @examples
#' cache <- datamonger_cache_dir(tempfile("datamonger-cache-"))
#' dir.create(cache)
#' cache_info(cache_dir = cache)
#' cache_clean(cache_dir = cache)
#' unlink(cache, recursive = TRUE)
#'
#' @rdname cache
#' @order 1
#' @export
datamonger_cache_dir <- function(cache_dir = NULL) {
  if (!is.null(cache_dir)) {
    return(path.expand(cache_dir))
  }

  file.path(tools::R_user_dir("datamonger", "cache"), "r")
}
