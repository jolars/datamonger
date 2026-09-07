\name{datamonger_cache_dir}
\alias{datamonger_cache_dir}
\alias{cache_info}
\alias{cache_clean}
\title{Select and Manage the Private R Cache}
\usage{
datamonger_cache_dir(cache_dir = NULL)

cache_info(cache_dir = NULL)

cache_clean(dataset = NULL, older_than = NULL, cache_dir = NULL)
}
\arguments{
  \item{cache_dir}{An explicit cache path, or \code{NULL} for the platform
  default.}
  \item{dataset}{A canonical \code{source:name@version} filter.}
  \item{older_than}{A nonnegative \code{difftime} or number of seconds.}
}
\description{
Datamonger uses the cache returned by \code{tools::R_user_dir()} by default. An
explicit path can select another persistent or temporary location. Eviction is
manual, and active objects are skipped.
}
\value{\code{datamonger_cache_dir()} returns a path without creating it.
\code{cache_info()} returns a cache inventory. \code{cache_clean()} reports
removed and skipped objects and the number of bytes removed.}
