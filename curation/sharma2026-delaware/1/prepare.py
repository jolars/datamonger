"""Convert pinned GeoGraphNetworks road graphs to gzip CSV tables."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen

SOURCES = {
    "delaware": (
        "https://ndownloader.figshare.com/files/51621923",
        339_748,
        "d170ec8f2c55398a5af9d00f252b16d5badebd36aa9a830198a30926524a6a65",
    ),
    "california": (
        "https://ndownloader.figshare.com/files/51621911",
        1_759_361,
        "cbb09f7403265f787fe892181b824a0fdc43b580d11506ca39d3287b34133c05",
    ),
    "texas": (
        "https://ndownloader.figshare.com/files/51622040",
        3_958_834,
        "b47f130069aba2be694253d66e143514c6be05e9a1839d8db14c0d739f6ad6d8",
    ),
}


def write_table(
    path: Path, header: tuple[str, ...], rows: Iterable[tuple[object, ...]]
) -> None:
    with (
        path.open("wb") as output,
        gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed,
        io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text,
    ):
        writer = csv.writer(text, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--state", choices=SOURCES, default="delaware")
    parser.add_argument(
        "--source", type=Path, help="Use a local copy of the source JSON"
    )
    args = parser.parse_args()

    url, size, sha256 = SOURCES[args.state]
    if args.source is None:
        with urlopen(url, timeout=30) as response:
            raw = response.read(size + 1)
    else:
        raw = args.source.read_bytes()
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("Source bytes differ from the pinned Figshare file")

    graph = json.loads(raw, parse_float=Decimal)
    args.output.mkdir(parents=True, exist_ok=True)
    write_table(
        args.output / "edges.csv.gz",
        ("source", "target", "weight"),
        ((edge["source"], edge["target"], edge["weight"]) for edge in graph["links"]),
    )
    write_table(
        args.output / "nodes.csv.gz",
        ("id", "x", "y"),
        ((node["id"], *node["pos"]) for node in graph["nodes"]),
    )


if __name__ == "__main__":
    main()
