\name{fetch_data}
\alias{fetch_data}
\alias{fetch_artifact}
\alias{data_info}
\alias{list_data}
\title{Retrieve or Inspect Registered Data}
\usage{
fetch_data(name, source = NULL, version = NULL, registry = NULL, cache_dir = NULL,
  offline = FALSE, verify_decoded = TRUE, return_info = FALSE)

fetch_artifact(name, source = NULL, version = NULL, artifact = NULL,
  registry = NULL, cache_dir = NULL, offline = FALSE)

data_info(name, source = NULL, version = NULL, registry = NULL, cache_dir = NULL,
  offline = FALSE)

list_data(registry = NULL, cache_dir = NULL, offline = FALSE)
}
\arguments{
  \item{name}{A bare dataset name, \code{source:name}, or
  \code{source:name@version}.}
  \item{source}{The dataset source. Required for bare names; omit it for
  qualified references, even if the values would agree.}
  \item{version}{An exact version. Omit it when the reference embeds a version,
  even if the values would agree. If neither form supplies a version, resolve
  the registry default.}
  \item{artifact}{An artifact name. It may be omitted for a single-artifact
  dataset.}
  \item{registry}{A strong selector, or \code{NULL} for the active selector.}
  \item{cache_dir}{An explicit cache path, or \code{NULL} for the platform
  default.}
  \item{offline}{Whether to forbid all network access.}
  \item{verify_decoded}{Whether to verify expected shape and canonical digest.}
  \item{return_info}{Whether to return reproducibility metadata with the data.}
}
\description{
Resolve a dataset within one strongly selected registry. Artifact size and
SHA-256 verification cannot be disabled. Decoded verification is enabled by
default and may be disabled only explicitly.
}
\value{\code{fetch_data()} returns a data frame or a Datamonger sparse result;
with \code{return_info = TRUE}, it returns a \code{datamonger_fetch_result}.
\code{fetch_artifact()} returns a cache path. Metadata functions return one or
a list of \code{datamonger_data_info} records. Sparse features use a
row-compressed \code{Matrix}, or an exact \code{datamonger_csr_matrix} when a
declared dimension exceeds the \code{Matrix} integer limit.}
