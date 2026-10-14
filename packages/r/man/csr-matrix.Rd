\name{datamonger_csr_matrix}
\alias{datamonger_csr_matrix}
\alias{dim.datamonger_csr_matrix}
\alias{print.datamonger_csr_matrix}
\title{Inspect a Sparse Matrix with Large Dimensions}
\usage{
\method{dim}{datamonger_csr_matrix}(x)

\method{print}{datamonger_csr_matrix}(x, ...)
}
\arguments{
  \item{x}{A \code{datamonger_csr_matrix} returned as sparse dataset features.}
  \item{...}{Additional arguments, ignored by the print method.}
}
\description{
Datamonger normally returns sparse features as a row-compressed \code{Matrix}.
When a declared dimension exceeds the \code{Matrix} integer limit, it returns
a \code{datamonger_csr_matrix} that retains the exact dimensions and CSR arrays.
These methods report its dimensions and a compact summary without allocating
a dense matrix.
}
\details{
The object contains \code{rows} and \code{columns}, zero-based
\code{row_offsets} and \code{column_indices}, and float64 \code{values}.
The print method reports the dimensions and the number of stored values.
}
\value{
\code{dim()} returns a numeric vector containing the row and column counts,
in that order. \code{print()} returns \code{x} invisibly.
}
\seealso{\code{\link{fetch_data}}}
