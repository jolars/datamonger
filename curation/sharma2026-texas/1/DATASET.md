# GeoGraphNetworks Texas road network

The Texas graph represents primary and secondary roads from the U.S. Census
Bureau's TIGER/Line data as prepared by GeoGraphNetworks. It contains 9,725 nodes
and 21,399 undirected edges. The tables retain the source IDs and row order. Both
tables are complete.

| File           |   Rows | Columns                                                                                                                         |
| -------------- | -----: | ------------------------------------------------------------------------------------------------------------------------------- |
| `edges.csv.gz` | 21,399 | `source` and `target` are integer node IDs. `weight` is the published edge length in kilometers.                                |
| `nodes.csv.gz` |  9,725 | `id` is the integer node ID. `x` and `y` are the two coordinates from the source node's `pos` field, in source order and units. |

The conversion keeps each undirected edge in the orientation supplied by the
source and preserves numeric values. Use either the published lengths or unit
weights when defining a graph penalty. Both tables describe graph topology and
attributes. They supply no prediction target.

Harish Sharma, Peter Mooney, and Edgar Galván-López published the source as
[GeoGraphNetworks, version 3](https://doi.org/10.6084/m9.figshare.27284859.v3).
The [data paper](https://doi.org/10.1016/j.dib.2026.112655) describes how the
authors derived the networks. The authors license the deposit under [CC BY
4.0](https://creativecommons.org/licenses/by/4.0/). Cite the authors and the
versioned deposit when reusing the data and indicate the conversion from the
source JSON to CSV.
