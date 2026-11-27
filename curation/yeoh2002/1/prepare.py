"""Prepare and validate the pinned stjudem release for Datamonger."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zlib
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402

SOURCE = "stjudem_1.16.0.tar.gz"
SOURCE_URL = (
    "https://ftp.gwdg.de/pub/misc/bioconductor/packages/3.5/data/experiment/src/contrib/"
    + SOURCE
)
SOURCE_SIZE = 28928034
SOURCE_SHA256 = "1b0a25f1ccf1f3d54f2430ed2a406d6afde25b32dddc0f64d525088fb07c0732"
COUNTS = {"BCR": 15, "E2A": 27, "Hyperdip": 64, "MLL": 20, "T": 43, "TEL": 79}


def sha256(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def download(url: str, path: Path) -> None:
    with urlopen(url, timeout=60) as response, path.open("wb") as target:
        shutil.copyfileobj(response, target)


def prepare(output: Path, local_source: Path | None) -> None:
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated data outside the working tree.")
    output.mkdir(mode=0o755)
    source = output / SOURCE
    if local_source is None:
        download(SOURCE_URL, source)
    else:
        shutil.copyfile(local_source, source)
    if source.stat().st_size != SOURCE_SIZE or sha256(source) != SOURCE_SHA256:
        raise ValueError("Archive differs from the reviewed stjudem release.")

    r_env = {
        key: value for key, value in os.environ.items() if key != "LD_LIBRARY_PATH"
    }
    r_env["LC_ALL"] = "C"
    data = output / "data.csv.gz"
    with tempfile.TemporaryDirectory(prefix="dm-stjudem-") as directory:
        temporary = Path(directory)
        rda = temporary / "stjude.rda"
        csv_path = temporary / "data.csv"
        source_bits = temporary / "expressions.bin"
        with tarfile.open(source, "r:gz") as archive:
            member = archive.extractfile("stjudem/data/stjude.rda")
            if member is None:
                raise ValueError("Missing stjude data object.")
            with member, rda.open("wb") as target:
                shutil.copyfileobj(member, target)
        subprocess.run(
            [
                "Rscript",
                "--vanilla",
                str(HERE / "convert.R"),
                rda,
                csv_path,
                source_bits,
            ],
            check=True,
            env=r_env,
        )
        with (
            csv_path.open("rb") as raw,
            data.open("wb") as target,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=target, mtime=0
            ) as compressed,
        ):
            shutil.copyfileobj(raw, compressed)
        csv_digest = sha256(csv_path)
        values = np.fromfile(source_bits, dtype="<u8").reshape(248, 12625)

    with gzip.open(data, "rt", encoding="utf-8", newline="") as stream:
        columns = next(csv.reader(stream))
    features = columns[1:-1]
    options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [
            {"name": name, "type": kind}
            for name, kind in zip(
                columns, ["string", *["float64"] * 12625, "string"], strict=True
            )
        ],
    }
    decoded = decode_delimited_text(data, options, compression="gzip")
    if (
        decoded.data.shape != (248, 12627)
        or columns[0] != "sample_id"
        or columns[-1] != "subtype"
        or not decoded.data["sample_id"].is_unique
        or decoded.data["subtype"].value_counts().to_dict() != COUNTS
        or any(not component.valid.all() for component in decoded.components)
    ):
        raise ValueError("Unexpected decoded dimensions, identifiers, or labels.")
    for index, component in enumerate(decoded.components[1:-1]):
        if not np.array_equal(component.values.view(np.uint64), values[:, index]):
            raise ValueError(f"Expression precision changed in {component.name}.")

    expectation = dm_add._expectation(decoded.components)
    manifest = dm_index.load_yaml(HERE / "manifest-template.yaml")
    manifest["artifacts"] = [
        {
            "name": "data",
            "format": "csv",
            "compression": "gzip",
            "size": data.stat().st_size,
            "sha256": sha256(data),
            "distribution": "metadata-only",
            "downloads": [],
        }
    ]
    manifest["representation"] = {
        "decoder": "delimited-text",
        "decoder_version": 1,
        "inputs": {"data": "data"},
        "options": options,
        "expect": expectation,
    }
    manifest["tasks"] = [
        {
            "name": "subtype",
            "type": "classification",
            "features": features,
            "target": "subtype",
        }
    ]
    dm_index.validate_manifest(manifest, root=ROOT)
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    provenance = {
        "source": {"url": SOURCE_URL, "size": SOURCE_SIZE, "sha256": SOURCE_SHA256},
        "artifact": {
            "size": data.stat().st_size,
            "sha256": sha256(data),
            "uncompressed_sha256": csv_digest,
        },
        "verification": expectation["verification"],
        "rows": 248,
        "predictors": 12625,
        "labels": COUNTS,
        "environment": {
            "python": platform.python_version(),
            "r": subprocess.check_output(
                ["Rscript", "--version"], env=r_env, text=True
            ).strip(),
            "zlib": zlib.ZLIB_RUNTIME_VERSION,
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="New directory outside the repository"
    )
    parser.add_argument("--source", type=Path, help="Reuse the exact reviewed archive")
    args = parser.parse_args()
    prepare(args.output, args.source)
