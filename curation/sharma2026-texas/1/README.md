# Preparing the GeoGraphNetworks Texas road network

The dataset ID is `datamonger:sharma2026-texas@1`. See
[DATASET.md](DATASET.md) for the source, attribution, and column definitions.
Use the [shared conversion recipe](../../sharma2026-delaware/1/prepare.py)
from the repository root in its devenv shell.

```console
python curation/sharma2026-delaware/1/prepare.py /tmp/sharma2026-texas --state texas
```

The recipe pins the versioned Figshare source by size and SHA-256. Use
`--source /path/to/texas.json` to reuse a local copy of those bytes.
The output uses delimited-text version 1. The registry representation returns the edge table. The deposit includes
the node table as a companion file.

Both CSV tables matched the source row for row and decoded to the expected
values in Datamonger's Python client. Two runs produced byte-identical gzip
files.

| Table | Canonical form 1 SHA-256                                           |
| ----- | ------------------------------------------------------------------ |
| Edges | `b5a36b2ce3a513f7e3453b31754f1f620ac36e7257bd52576ebfa6a59ba6128b` |
| Nodes | `3577d618ed3dea2edd2c1c4bcc72e7854af5c6be1d6e5617698666e38fbe0393` |

## Deposit and registration

The [version 1 Zenodo deposit](https://doi.org/10.5281/zenodo.24400344) contains
both CSV files and the public documentation as `README.md`. All three
anonymous downloads matched the prepared files, and the deposit retains
CC BY 4.0. See [the receipt](zenodo-record.json) for direct download links
and verified SHA-256 digests.

The [manifest](../../../registry/datasets/datamonger/sharma2026-texas-1.yaml)
is selected in the registry collection for the next release.
