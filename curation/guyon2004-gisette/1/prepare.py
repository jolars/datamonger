"""Prepare the original Gisette values and splits from UCI without scaling."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import platform
import shutil
import subprocess
import sys
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402
from datamonger._decode_libsvm import decode_libsvm_split  # noqa: E402

DATASET_ID = "datamonger:guyon2004-gisette@1"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/170/gisette.zip"
SOURCE_SIZE = 21298687
SOURCE_SHA256 = "430bb631b3e494659f13763c117f06f5aa8a269b0d8e13ccf5b71d95303f3808"
LANDING_PAGE = "https://archive.ics.uci.edu/dataset/170/gisette"
PAPER_URL = (
    "https://proceedings.neurips.cc/paper_files/paper/2004/hash/"
    "5e751896e527c862bf67251a474b3819-Abstract.html"
)
FEATURE_COUNT = 5000
SPLITS = {
    "train": (
        "GISETTE/gisette_train.data",
        "GISETTE/gisette_train.labels",
        6000,
        3164568508,
    ),
    "validation": (
        "GISETTE/gisette_valid.data",
        "gisette_valid.labels",
        1000,
        535016668,
    ),
    "test": ("GISETTE/gisette_test.data", None, 6500, 3431572010),
}
LIBSVM_OPTIONS = {
    "index_base": 1,
    "feature_count": FEATURE_COUNT,
    "duplicate_features": "error",
    "label_type": "int64",
    "row_order": "source",
    "target_name": "response",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def convert_split(archive: ZipFile, split: str, output: Path) -> dict[str, object]:
    """Preserve every row, feature position, integer value, and available label."""
    member, label_member, expected_rows, expected_sum = SPLITS[split]
    labels = None
    if label_member is not None:
        labels = [int(value) for value in archive.read(label_member).split()]
        if Counter(labels) != {-1: expected_rows // 2, 1: expected_rows // 2}:
            raise ValueError(f"Unexpected {split} label counts.")
    count = total = nonzeros = 0
    minimum, maximum = 999, 0
    # Fixed gzip metadata makes the artifacts repeatable in the recorded environment.
    with (
        archive.open(member) as source,
        output.open("wb") as raw,
        gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6
        ) as compressed,
        io.TextIOWrapper(compressed, encoding="ascii", newline="\n") as target,
    ):
        writer = csv.writer(target, lineterminator="\n")
        if labels is None:
            writer.writerow(f"x{index}" for index in range(1, FEATURE_COUNT + 1))
        for row_index, line in enumerate(source):
            if row_index >= expected_rows:
                raise ValueError(f"Too many {split} rows.")
            values = [int(token) for token in line.split()]
            if len(values) != FEATURE_COUNT or min(values) < 0 or max(values) > 999:
                raise ValueError(f"Unexpected {split} feature count or value range.")
            count += 1
            total += sum(values)
            minimum, maximum = min(minimum, min(values)), max(maximum, max(values))
            nonzeros += sum(value != 0 for value in values)
            if labels is None:
                writer.writerow(values)
            else:
                fields = [str(labels[row_index])]
                fields.extend(
                    f"{index}:{value}"
                    for index, value in enumerate(values, 1)
                    if value != 0
                )
                target.write(" ".join(fields) + "\n")
    if count != expected_rows or total != expected_sum:
        raise ValueError(f"{split} dimensions or checksum differ from gisette.param.")
    return {
        "rows": count,
        "features": FEATURE_COUNT,
        "value_min": minimum,
        "value_max": maximum,
        "nonzeros": nonzeros,
        "sum": total,
        "labels": dict(sorted(Counter(labels).items())) if labels is not None else None,
    }


def prepare(output: Path, source: Path | None = None) -> None:
    """Create and verify a local bundle without uploading or publishing files."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    archive_path = sources / "gisette.zip"
    if source is None:
        with (
            urlopen(SOURCE_URL, timeout=60) as response,
            archive_path.open("wb") as target,
        ):
            shutil.copyfileobj(response, target)
    else:
        shutil.copyfile(source, archive_path)
    if (
        archive_path.stat().st_size != SOURCE_SIZE
        or sha256(archive_path) != SOURCE_SHA256
    ):
        raise ValueError("UCI archive differs from its pinned size and SHA-256.")

    filenames = {
        "train": "train.libsvm.gz",
        "validation": "validation.libsvm.gz",
        "test": "test-features.csv.gz",
    }
    with ZipFile(archive_path) as archive:
        split_facts = {
            split: convert_split(archive, split, output / filename)
            for split, filename in filenames.items()
        }
        member_facts = {}
        for name in archive.namelist():
            if not name.endswith("/"):
                with archive.open(name) as stream:
                    member_facts[name] = {
                        "size": archive.getinfo(name).file_size,
                        "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
                    }

    labeled = decode_libsvm_split(
        output / filenames["train"],
        output / filenames["validation"],
        LIBSVM_OPTIONS,
        train_compression="gzip",
        test_compression="gzip",
    )
    expectation = dm_add._expectation(labeled.components)
    del labeled
    test_options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [
            {"name": f"x{index}", "type": "int64"}
            for index in range(1, FEATURE_COUNT + 1)
        ],
    }
    test = decode_delimited_text(
        output / filenames["test"], test_options, compression="gzip"
    )
    test_expectation = dm_add._expectation(test.components)
    del test
    rights = {
        "status": "known",
        "identifier": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "evidence": (
            f"The UCI Gisette landing page ({LANDING_PAGE}) explicitly licenses "
            "the dataset under CC BY 4.0. This representation preserves the "
            "original feature values, available labels, and split membership; "
            "it changes file encoding and compression only."
        ),
    }
    artifacts = [
        {
            "name": split,
            "format": "csv" if split == "test" else "libsvm",
            "compression": "gzip",
            "size": (output / filename).stat().st_size,
            "sha256": sha256(output / filename),
            "distribution": "metadata-only",
            "downloads": [],
        }
        for split, filename in filenames.items()
    ]
    manifest = {
        "schema_version": 3,
        "source": "datamonger",
        "name": "guyon2004-gisette",
        "version": "1",
        "title": "Gisette: original challenge feature values",
        "description": (
            "Digit 4-versus-9 classification data from the NIPS 2003 feature "
            "selection challenge, prepared from UCI without further scaling. "
            "Preserves 6,000 training rows and 1,000 validation rows with 5,000 "
            "features and original -1/+1 labels. The unlabeled 6,500-row test "
            "set is retained as a separate CSV artifact outside the labeled "
            "representation. Feature identities and label-to-digit mappings "
            "are not established."
        ),
        "modality": "tabular",
        "preprocessing": {
            "upstream": {
                "status": "documented",
                "evidence": [LANDING_PAGE],
                "steps": [
                    {
                        "kind": "feature-encoding",
                        "description": (
                            "The producers normalize and center digit images, sample "
                            "pixels, construct pixel products, add distractor probes, "
                            "and randomize feature and example order."
                        ),
                    }
                ],
                "notes": (
                    "These are prepared challenge features, not raw images. "
                    "The UCI integers range from 0 to 999. No LIBSVM scaling is used."
                ),
            },
            "datamonger": {
                "status": "none",
                "evidence": [
                    "curation/guyon2004-gisette/1/prepare.py",
                    "curation/guyon2004-gisette/1/DATASET.md",
                ],
                "notes": (
                    "Only lossless file conversion and gzip compression are applied. "
                    "Feature values, labels, ordering, and source splits are preserved."
                ),
            },
        },
        "provenance": {
            "provider": "Datamonger; derived from UCI Gisette",
            "upstream_name": "Gisette",
            "upstream_id": "170",
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "landing_page": LANDING_PAGE,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": ["Isabelle Guyon", "Steve Gunn", "Asa Ben-Hur", "Gideon Dror"],
            "citations": [
                {
                    "citation": (
                        "Guyon, I., Gunn, S., Ben-Hur, A., and Dror, G. (2004). "
                        "Gisette [Dataset]. UCI Machine Learning Repository. "
                        "https://doi.org/10.24432/C5HP5B."
                    ),
                    "role": "dataset",
                },
                {
                    "citation": (
                        "Guyon, I., Gunn, S., Ben-Hur, A., and Dror, G. (2004). "
                        "Result Analysis of the NIPS 2003 Feature Selection Challenge. "
                        "Advances in Neural Information Processing Systems 17. "
                        f"{PAPER_URL}"
                    ),
                    "role": "paper",
                },
            ],
        },
        "license": rights,
        "artifacts": artifacts,
        "representation": {
            "decoder": "libsvm-split",
            "decoder_version": 1,
            "inputs": {"train": "train", "test": "validation"},
            "options": LIBSVM_OPTIONS,
            "expect": expectation,
        },
        "tasks": [
            {
                "name": "default",
                "type": "classification",
                "splits": {
                    "train": {"features": "train_features", "target": "train_response"},
                    "validation": {
                        "features": "test_features",
                        "target": "test_response",
                    },
                },
            }
        ],
    }
    dm_index.validate_manifest(manifest, root=ROOT)
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    test_representation = {
        "decoder": "delimited-text",
        "decoder_version": 1,
        "inputs": {"data": "test"},
        "options": test_options,
        "expect": test_expectation,
    }
    (output / "test-representation.local.yaml").write_text(
        yaml.safe_dump(test_representation, sort_keys=False), encoding="utf-8"
    )
    for name in ("prepare.py", "verify.py"):
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    provenance = {
        "dataset_id": DATASET_ID,
        "source": {"url": SOURCE_URL, "size": SOURCE_SIZE, "sha256": SOURCE_SHA256},
        "source_acquisition": "download" if source is None else "local file",
        "source_members": member_facts,
        "splits": split_facts,
        "environment": {
            "python": platform.python_version(),
            "zlib": zlib.ZLIB_RUNTIME_VERSION,
            "devenv_lock_sha256": sha256(ROOT / "devenv.lock"),
            "uv_lock_sha256": sha256(ROOT / "packages/python/uv.lock"),
        },
        "labeled_verification": expectation["verification"],
        "test_verification": test_expectation["verification"],
        "files": {
            name: {
                "size": (output / name).stat().st_size,
                "sha256": sha256(output / name),
            }
            for name in (
                *filenames.values(),
                "prepare.py",
                "verify.py",
                "README.md",
                "LICENSE",
            )
        },
        "source_terms": rights,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("verify.py")), str(output)],
        check=True,
    )
    print(f"Prepared and verified {DATASET_ID}: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    parser.add_argument("--source", type=Path, help="reuse the pinned UCI ZIP archive")
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.source)
