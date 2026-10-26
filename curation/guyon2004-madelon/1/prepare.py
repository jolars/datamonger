"""Convert pinned UCI Madelon matrices into lossless, named CSV splits."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import shutil
import sys
import zlib
from collections import Counter
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "packages/python/tests"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402
from reference._canonical import canonical_sha256 as reference_sha256  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402
from datamonger._splits import assemble_splits  # noqa: E402

SOURCE_URL = "https://archive.ics.uci.edu/static/public/171/madelon.zip"
SOURCE_SHA256 = "eb99a0153ebe7d9f4e74551b4b10c54a958b2990b156ce7d76b4e8d71a6f6e82"
SOURCE_SIZE = 3040503
LANDING_PAGE = "https://archive.ics.uci.edu/dataset/171/madelon"
SPLITS = {
    "train": (
        "MADELON/madelon_train.data",
        "MADELON/madelon_train.labels",
        2000,
        488083511,
    ),
    "validation": (
        "MADELON/madelon_valid.data",
        "madelon_valid.labels",
        600,
        146395833,
    ),
    "test": ("MADELON/madelon_test.data", None, 1800, 439209553),
}


def facts(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"size": path.stat().st_size, "sha256": digest}


def prepare(output: Path, source: Path | None) -> None:
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Generated artifacts must stay outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    archive_path = output / "madelon.zip"
    if source is None:
        with (
            urlopen(SOURCE_URL, timeout=60) as response,
            archive_path.open("wb") as target,
        ):
            shutil.copyfileobj(response, target)
    else:
        shutil.copyfile(source, archive_path)
    if facts(archive_path) != {"size": SOURCE_SIZE, "sha256": SOURCE_SHA256}:
        raise ValueError("Source differs from the pinned UCI archive.")

    artifacts, recipes, children, roles = [], [], [], {}
    split_facts, members = {}, {}
    with ZipFile(archive_path) as archive:
        for name in archive.namelist():
            if not name.endswith("/"):
                members[name] = {
                    "size": archive.getinfo(name).file_size,
                    "sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                }
        for split, (member, label_member, rows, checksum) in SPLITS.items():
            columns = [{"name": f"x{i}", "type": "int64"} for i in range(1, 501)]
            labels = None
            if label_member:
                labels = [int(token) for token in archive.read(label_member).split()]
                if Counter(labels) != {-1: rows // 2, 1: rows // 2}:
                    raise ValueError(f"Unexpected {split} labels.")
                columns.append({"name": "response", "type": "int64"})
            path = output / f"{split}.csv.gz"
            count = total = 0
            # Fixed metadata avoids timestamps and local filenames in gzip bytes.
            with (
                archive.open(member) as stream,
                path.open("wb") as raw,
                gzip.GzipFile(
                    filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6
                ) as compressed,
                io.TextIOWrapper(compressed, encoding="ascii", newline="\n") as target,
            ):
                writer = csv.writer(target, lineterminator="\n")
                writer.writerow(column["name"] for column in columns)
                for index, line in enumerate(stream):
                    values = [int(token) for token in line.split()]
                    if len(values) != 500 or index >= rows:
                        raise ValueError(f"Unexpected {split} dimensions.")
                    count += 1
                    total += sum(values)
                    writer.writerow(
                        values if labels is None else [*values, labels[index]]
                    )
            if count != rows or total != checksum:
                raise ValueError(f"{split} disagrees with madelon.param.")
            options = {
                "encoding": "utf-8",
                "delimiter": ",",
                "header": True,
                "quote": '"',
                "escape": "double",
                "missing_values": [],
                "row_order": "source",
                "columns": columns,
            }
            child = decode_delimited_text(path, options, compression="gzip")
            # NumPy provides an independent parser for the source values.
            with archive.open(member) as stream:
                expected = np.loadtxt(stream, dtype=np.int64)
            if expected.shape != (rows, 500):
                raise ValueError(f"Unexpected source shape for {split}.")
            for index, component in enumerate(child.components[:500]):
                np.testing.assert_array_equal(component.values, expected[:, index])
            if label_member:
                with archive.open(label_member) as stream:
                    np.testing.assert_array_equal(
                        child.components[-1].values, np.loadtxt(stream, dtype=np.int64)
                    )
            if not all(component.valid.all() for component in child.components):
                raise ValueError("Unexpected missing values.")
            children.append(child)
            recipes.append(
                {
                    "name": split,
                    "decoder": "delimited-text",
                    "decoder_version": 1,
                    "options": options,
                }
            )
            artifacts.append(
                {
                    "name": split,
                    "format": "csv",
                    "compression": "gzip",
                    **facts(path),
                    "distribution": "metadata-only",
                    "downloads": [],
                }
            )
            roles[split] = {"features": [f"{split}/x{i}" for i in range(1, 501)]}
            if labels is not None:
                roles[split]["target"] = f"{split}/response"
            split_facts[split] = {
                "rows": rows,
                "features": 500,
                "sum": total,
                "min": int(expected.min()),
                "max": int(expected.max()),
                "labels": dict(Counter(labels)) if labels is not None else None,
            }
    decoded = assemble_splits(recipes, children)
    expectation = dm_add._expectation(decoded.components)
    digest = expectation["verification"][0]["digest"]
    if reference_sha256(decoded.components) != digest:
        raise ValueError("Rust and independent Python canonical encoders disagree.")
    manifest = {
        "schema_version": 5,
        "source": "datamonger",
        "name": "guyon2004-madelon",
        "version": "1",
        "title": "Madelon: original UCI challenge splits",
        "description": (
            "Synthetic binary classification benchmark preserving all 500 "
            "features and the original training, validation, and unlabeled test splits."
        ),
        "modality": "tabular",
        "preprocessing": {
            "upstream": {
                "status": "documented",
                "evidence": [LANDING_PAGE],
                "steps": [
                    {
                        "kind": "synthetic-generation",
                        "description": (
                            "Generate five informative dimensions, 15 redundant "
                            "linear combinations, and 480 distractors; randomize "
                            "feature and observation order."
                        ),
                    }
                ],
            },
            "datamonger": {
                "status": "none",
                "evidence": ["curation/guyon2004-madelon/1/prepare.py"],
                "notes": (
                    "Lossless CSV conversion and gzip compression only. "
                    "Preserve all values, labels, row and feature order, and splits."
                ),
            },
        },
        "provenance": {
            "provider": "Datamonger; derived from UCI",
            "upstream_name": "Madelon",
            "upstream_id": "171",
            "landing_page": LANDING_PAGE,
            "authors": ["Isabelle Guyon"],
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "citations": [
                {
                    "citation": (
                        "Guyon, I. (2004). Madelon [Dataset]. "
                        "UCI Machine Learning Repository. https://doi.org/10.24432/C5602H."
                    ),
                    "role": "dataset",
                }
            ],
        },
        "license": {
            "status": "known",
            "identifier": "CC-BY-4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
            "evidence": (
                f"UCI explicitly licenses Madelon under CC BY 4.0: {LANDING_PAGE}."
            ),
        },
        "artifacts": artifacts,
        "representation": {
            "decoder": "named-splits",
            "decoder_version": 1,
            "inputs": {split: split for split in SPLITS},
            "options": {"splits": recipes},
            "expect": expectation,
        },
        "tasks": [{"name": "default", "type": "classification", "splits": roles}],
    }
    # Retrieval dates describe actual acquisition, rather than the archive's vintage.
    from datetime import UTC, datetime

    manifest["provenance"]["retrieved_at"] = datetime.now(UTC).date().isoformat()
    dm_index.validate_manifest(manifest, root=ROOT)
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    receipt = {
        "dataset_id": "datamonger:guyon2004-madelon@1",
        "stage": "local preparation",
        "registered": False,
        "deposit": None,
        "source": {"url": SOURCE_URL, **facts(archive_path)},
        "source_members": members,
        "splits": split_facts,
        "files": {
            f"{split}.csv.gz": facts(output / f"{split}.csv.gz") for split in SPLITS
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "zlib": zlib.ZLIB_RUNTIME_VERSION,
            "devenv_lock": facts(ROOT / "devenv.lock"),
            "uv_lock": facts(ROOT / "packages/python/uv.lock"),
        },
        "verification": {
            "feature_values_compared": 2200000,
            "labels_compared": 2600,
            "source_checksums": "passed",
            "canonical_sha256": digest,
            "rust_and_reference_python": "agree",
            "independent_release_attestation": False,
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Verified 2,200,000 feature values and 2,600 labels; output: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--source", type=Path, help="Use a pinned local ZIP for offline reproduction."
    )
    args = parser.parse_args()
    prepare(args.output, args.source)
