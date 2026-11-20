# Graph tables and HIF decoder version 1

Manifest and index schema 8 add `graph-tables` and `hif` decoder version 1.
An index may mix manifest versions 1 through 8. Both decoders accept artifact
compression `none`, `gzip`, and `bzip2`.

## Graph tables

Use modality `graph`. The `nodes` and `edges` inputs select CSV or TSV
artifacts. Options contain the boolean `directed` and a complete
[delimited-text version 1 recipe](delimited-text-v1.md) under each input role.

Nodes have a unique, non-null `id` column of type `int64` or `string`.
Edges have non-null `source` and `target` columns of the same type, and both
must refer to node IDs. An optional edge `id` follows the same rules as the
node key. All other columns are attributes. Both tables retain source row and
column order, including isolates, self-loops, and parallel edges.

## HIF

Use modality `hypergraph` and a single `data` input with artifact format
`hif`. Options contain the boolean `directed`, the `node_id` and `edge_id`
types (`int64` or `string`), and column specifications under `nodes`,
`hyperedges`, and `incidences`. Each specification contains a boolean
`weight` and an ordered array of `attributes` with `name` and `type`. Attribute
types are `int64`, `float64`, `string`, and `bool`.

The JSON artifact contains `incidences` and may contain `nodes`, `edges`,
`network-type`, and an object named `metadata`. Network type must match the
recipe and defaults to undirected when absent. Explicit entity records use
`node` or `edge` keys. Incidences use both and retain source order. Explicit
nodes and hyperedges come first in each table, followed by entities inferred
in first incidence order. Entity output keys are named `id`. Incidence output
keys are `node` and `edge`, followed by `direction` for directed hypergraphs.
Directed memberships use `head` or `tail`. Memberships must be unique, including
direction when present.

An enabled top-level `weight` produces a nullable float64 column after the
structural columns. Declared `attrs` follow in recipe order. Missing
attributes and weights are null, including on inferred entities. Attribute
names must be unique within each table and must avoid the table's structural
names and any enabled weight column. Undeclared attributes and weights are
decode errors.

## Verification and client results

Canonical form 1 starts with a length-one, valid boolean vector named
`directed`. The ordered table columns follow, with names prefixed by
`nodes/`, then `edges/` for graphs or `hyperedges/` and `incidences/` for
hypergraphs. Public tables expose the original column names. Turning off
decoded verification still requires verified artifact bytes and valid topology.
