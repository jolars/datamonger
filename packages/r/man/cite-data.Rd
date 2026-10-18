\name{cite_data}
\alias{cite_data}
\title{Get Curated Dataset Citations}
\usage{
cite_data(name, source = NULL, version = NULL, registry = NULL,
  cache_dir = NULL, offline = FALSE, include_all = FALSE, format = "text")
}
\arguments{
  \item{name}{A bare dataset name, \code{source:name}, or \code{source:name@version}.}
  \item{source}{Dataset source. Required for bare names; omit for qualified references.}
  \item{version}{Exact dataset version. Omit when embedded in \code{name}.
  An omitted version selects the registry default.}
  \item{registry}{A strong selector, or \code{NULL} for the active selector.}
  \item{cache_dir}{An explicit cache directory, or \code{NULL} for the platform default.}
  \item{offline}{Whether to use only bundled or verified cached registry bytes.}
  \item{include_all}{Whether to include every reference regardless of recommendation.}
  \item{format}{Either \code{"text"} or \code{"records"}.}
}
\description{
Retrieve curated citations from the selected registry without downloading
artifacts or looking up bibliographic identifiers. Multiple references can be
recommended together. Optional roles describe a dataset, paper, or collection;
roles do not imply recommendations.
}
\details{
By default, return references explicitly marked as recommended by upstream. If
no reference carries a recommendation flag, return all references and explain
the unknown recommendation in text output. If flags exist but none is true,
return an empty selection. Missing citation metadata produces an explicit text
message or an empty list. The legacy single citation remains supported.

All references and upstream instructions are also available as \code{citations}
and \code{citation_instructions} in \code{data_info()} and fetch metadata from
\code{fetch_data(return_info = TRUE)}. An absent recommendation flag means
unknown, whereas \code{FALSE} records that the reference is not recommended.
}
\value{
A character string with role labels, notes, and upstream instructions, or a list
of citation records with optional \code{role}, \code{note}, and
\code{recommended} fields preserved.
}
\seealso{\code{\link{data_info}}, \code{\link{fetch_data}}}
