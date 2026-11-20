"""Convert the pinned GeoGraphNetworks Delaware graph to gzip CSV tables."""

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

SOURCE_URL = "https://ndownloader.figshare.com/files/51621923"
SOURCE_SIZE = 339_748
SOURCE_SHA256 = "d170ec8f2c55398a5af9d00f252b16d5badebd36aa9a830198a30926524a6a65"


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
    parser.add_argument("--source", type=Path, help="Use a local copy of delaware.json")
    args = parser.parse_args()

    if args.source is None:
        with urlopen(SOURCE_URL, timeout=30) as response:
            raw = response.read(SOURCE_SIZE + 1)
    else:
        raw = args.source.read_bytes()
    if len(raw) != SOURCE_SIZE or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
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
