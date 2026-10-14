\name{datamonger_int64}
\alias{datamonger_int64}
\alias{format.datamonger_int64}
\alias{print.datamonger_int64}
\title{Display Exact 64-bit Integer Values}
\usage{
\method{format}{datamonger_int64}(x, ...)

\method{print}{datamonger_int64}(x, ...)
}
\arguments{
  \item{x}{A \code{datamonger_int64} vector returned in decoded data.}
  \item{...}{For \code{print()}, additional arguments passed to the character
  vector print method, except \code{quote}, which is fixed to \code{FALSE}.
  The format method ignores these arguments.}
}
\description{
Datamonger stores signed 64-bit integers as decimal character strings so that
values outside R's exact numeric range retain all their digits. These methods
display those strings without converting them to floating-point numbers.
}
\details{
Missing values are stored as \code{NA_character_}. The format method removes
the Datamonger class and retains the underlying strings and missing values.
The print method displays the formatted vector without quotation marks.
}
\value{
\code{format()} returns the underlying character vector.
\code{print()} returns \code{x} invisibly.
}
\seealso{\code{\link{fetch_data}}}
