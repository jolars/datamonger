\name{registry_selector}
\alias{registry_selector}
\alias{resolve_registry}
\alias{set_registry}
\alias{active_registry}
\title{Select an Immutable Registry Release}
\usage{
registry_selector(release, index_sha256, index_url, schema_version = 1L)

resolve_registry(release, catalog_url = NULL)

set_registry(registry)

active_registry(project_dir = getwd())
}
\arguments{
  \item{release}{A registry release identifier.}
  \item{index_sha256}{The lowercase SHA-256 of the exact index bytes.}
  \item{index_url}{An absolute HTTP or HTTPS retrieval URL.}
  \item{schema_version}{The selector schema version.}
  \item{catalog_url}{An HTTPS catalog URL. The package default is used when
  this is \code{NULL}.}
  \item{registry}{A strong registry selector, or \code{NULL} to clear the
  session setting.}
  \item{project_dir}{The directory from which to search upward for a project
  selector.}
}
\description{
Construct, discover, set, or inspect a strong registry selector. A catalog
lookup is TLS-trusted discovery; recording and reusing its returned release and
digest creates the reproducible selector.
}
\value{\code{registry_selector()}, \code{resolve_registry()}, and
\code{active_registry()} return a \code{datamonger_registry}. The setter
returns \code{NULL} invisibly.}
