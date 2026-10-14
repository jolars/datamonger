\name{datamonger_metadata}
\alias{datamonger_metadata}
\alias{datamonger_registry}
\alias{datamonger_fetch_info}
\alias{datamonger_data_info}
\alias{datamonger_cache_info}
\alias{print.datamonger_registry}
\alias{print.datamonger_fetch_info}
\alias{print.datamonger_data_info}
\alias{print.datamonger_cache_info}
\title{Display Registry, Fetch, Dataset, and Cache Metadata}
\usage{
\method{print}{datamonger_registry}(x, ...)

\method{print}{datamonger_fetch_info}(x, ...)

\method{print}{datamonger_data_info}(x, ...)

\method{print}{datamonger_cache_info}(x, ...)
}
\arguments{
  \item{x}{A Datamonger registry selector, fetch metadata record, dataset
  metadata record, or cache inventory matching the method's class.}
  \item{...}{Additional arguments, ignored by these print methods.}
}
\description{
Print compact summaries of Datamonger metadata objects. The methods read the
object's fields without retrieving data or inspecting the cache again.
}
\details{
Registry selectors returned by \code{registry_selector()},
\code{resolve_registry()}, or \code{active_registry()} display the release,
index SHA-256, and index URL.

The \code{info} member returned by \code{fetch_data(return_info = TRUE)}
displays the resolved dataset identifier, registry release, and completed
verification level.

Dataset records returned by \code{data_info()} or in the list returned by
\code{list_data()} display the resolved dataset identifier, title, and
registry release.

Cache inventories returned by \code{cache_info()} display the cache location,
entry count, and total size in bytes. These summaries describe the inventory
at the time it was collected.
}
\value{Each print method returns \code{x} invisibly.}
\seealso{
\code{\link{registry_selector}}, \code{\link{fetch_data}},
\code{\link{data_info}}, \code{\link{cache_info}}
}
