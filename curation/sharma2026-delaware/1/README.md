# Preparing the GeoGraphNetworks Delaware road network

The dataset ID is `datamonger:sharma2026-delaware@1`. The source is
`delaware.json` from version 3 of the authors' Figshare deposit. Figshare
identifies the data license as CC BY 4.0 in the [version 3
metadata](https://api.figshare.com/v2/articles/27284859/versions/3). See
[DATASET.md](DATASET.md) for attribution, column definitions, and the conversion
applied to the published graph.

Run from the repository root in the devenv shell. The recipe uses the Python
standard library and checks the source size and SHA-256 before conversion.

```console
python curation/sharma2026-delaware/1/prepare.py /tmp/sharma2026-delaware
```

Use `--source /path/to/delaware.json` to reuse a local copy of the pinned input.
The script emits headered, UTF-8 CSV tables with deterministic gzip metadata.
The columns use `int64` for node IDs and `float64` for weights and coordinates.
Each table can be decoded with delimited-text version 1. The registry
representation returns the edge table. The node table is a companion file in
the same deposit.

## Verification

The two tables matched the source JSON row for row and decoded to the expected
values with Datamonger's Python client. Two runs in the repository's devenv
shell produced byte-identical gzip files.

  | Table | Canonical form 1 SHA-256                                           |
  | ----- | ------------------------------------------------------------------ |
  | Edges | `af4c41e5135010c4f01fd14ff8571969809bd4f034155d69299ba1f64659c6b6` |
  | Nodes | `b3f3ffdc1ded0e2a2bf52c4b81d796b367ab7127b32402e51d2c4aa97ca211b0` |

## Deposit and registration

The [version 1 Zenodo deposit](https://doi.org/10.5281/zenodo.24399892) contains
both CSV files and the public documentation as `README.md`. All three
anonymous downloads matched the prepared files and the deposit retains
CC BY 4.0. See [the receipt](zenodo-record.json) for the direct download links
and verified SHA-256 digests.

The [manifest](../../../registry/datasets/datamonger/sharma2026-delaware-1.yaml)
is selected in the registry collection for the next release.
