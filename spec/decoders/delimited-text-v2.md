# Delimited Text Decoder Version 2

This document is normative for `delimited-text` version `2`. Use manifest
schema version `5` to select this decoder, including as a child of
`named-splits` version `1`.

Version 2 follows [version 1](delimited-text-v1.md) and accepts either a comma
(`,`) or a semicolon (`;`) for an artifact with `format: csv`. An artifact with
`format: tsv` requires a horizontal tab. The manifest explicitly declares
the delimiter. The same quoting, escaping, and canonical verification rules
apply with each delimiter.
