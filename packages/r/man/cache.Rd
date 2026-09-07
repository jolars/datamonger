\name{datamonger_cache_dir}
\alias{datamonger_cache_dir}
\alias{cache_info}
\alias{cache_clean}
\title{Select and Manage the Private R Cache}
\usage{
datamonger_cache_dir(cache_dir = NULL, .interactive = interactive(),
  .ask = utils::askYesNo)

cache_info(cache_dir = NULL)

cache_clean(dataset = NULL, older_than = NULL, cache_dir = NULL)
}
\arguments{
  \item{cache_dir}{An explicit cache path, or \code{NULL} to apply the consent
  policy.}
  \item{.interactive}{Whether to offer an interactive consent prompt.}
  \item{.ask}{The yes-or-no prompt function.}
  \item{dataset}{A canonical \code{source:name@version} filter.}
  \item{older_than}{A nonnegative \code{difftime} or number of seconds.}
}
\description{
Datamonger uses \code{tools::R_user_dir()} only after explicit consent through
the \code{datamonger.cache_consent} option or an interactive prompt. Otherwise,
it uses the R session temporary directory. Eviction is manual, and active
objects are skipped.
}
\value{\code{datamonger_cache_dir()} returns a path without creating it.
\code{cache_info()} returns a cache inventory. \code{cache_clean()} reports
removed and skipped objects and the number of bytes removed.}
