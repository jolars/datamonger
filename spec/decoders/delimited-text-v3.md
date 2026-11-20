# Delimited Text Decoder Version 3

Version 3 follows [version 2](delimited-text-v2.md) with two layout options.

- `skip_lines` is an optional integer from 0 through 4294967295 and defaults
  to 0. Discard exactly this many leading physical lines before parsing the
  table. The discarded lines must follow the encoding and line-ending rules
  but may contain arbitrary text. Reaching the end of input before discarding
  the declared number of lines is an error.
- `header` is a required boolean. If true, the first remaining record must
  match the declared column names. If false, every remaining record is a data
  row and the manifest supplies the column names. A headerless input with no
  remaining records produces zero-length components.

For SNAP road networks such as `roadNet-CA`, use `skip_lines: 4` and
`header: false` with two integer columns. The decoder retains source row
order, including rows with reversed endpoint pairs.
