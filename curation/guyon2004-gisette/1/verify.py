"""Compare every converted Gisette value and label with the pinned UCI archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages/python/tests"))

from reference._canonical import canonical_sha256 as reference_sha256  # noqa: E402

from datamonger._canonical import canonical_sha256  # noqa: E402
from datamonger._decode import decode_delimited_text  # noqa: E402
from datamonger._decode_libsvm import decode_libsvm_split  # noqa: E402

SOURCE_SIZE = 21298687
SOURCE_SHA256 = "430bb631b3e494659f13763c117f06f5aa8a269b0d8e13ccf5b71d95303f3808"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(bundle: Path) -> None:
    """Use NumPy's text reader independently of the conversion's row parser."""
    archive_path = bundle / "sources/gisette.zip"
    if (
        archive_path.stat().st_size != SOURCE_SIZE
        or sha256(archive_path) != SOURCE_SHA256
    ):
        raise ValueError("Source archive differs from its pinned size and SHA-256.")
    receipt = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))
    for name, facts in receipt["files"].items():
        path = bundle / name
        if path.stat().st_size != facts["size"] or sha256(path) != facts["sha256"]:
            raise ValueError(f"Prepared file differs from its receipt: {name}")
    manifest = yaml.safe_load((bundle / "manifest.local.yaml").read_text())
    representation = manifest["representation"]
    labeled = decode_libsvm_split(
        bundle / "train.libsvm.gz",
        bundle / "validation.libsvm.gz",
        representation["options"],
        train_compression="gzip",
        test_compression="gzip",
    )
    with ZipFile(archive_path) as archive:
        for member, label_member, decoded, rows in (
            (
                "GISETTE/gisette_train.data",
                "GISETTE/gisette_train.labels",
                labeled.data.train,
                6000,
            ),
            (
                "GISETTE/gisette_valid.data",
                "gisette_valid.labels",
                labeled.data.test,
                1000,
            ),
        ):
            with archive.open(member) as stream:
                expected = np.loadtxt(stream, dtype=np.int64)
            with archive.open(label_member) as stream:
                labels = np.loadtxt(stream, dtype=np.int64)
            if (
                expected.shape != (rows, 5000)
                or decoded.features.shape != expected.shape
            ):
                raise ValueError(f"Unexpected feature dimensions: {member}")
            for row in range(rows):
                np.testing.assert_array_equal(
                    decoded.features.getrow(row).toarray()[0], expected[row]
                )
            np.testing.assert_array_equal(decoded.response, labels)
            del expected
        digest = canonical_sha256(labeled.components)
        if digest != representation["expect"]["verification"][0]["digest"]:
            raise ValueError(
                "Labeled canonical digest differs from the local manifest."
            )
        if reference_sha256(labeled.components) != digest:
            raise ValueError(
                "Native and independent Python canonical encoders disagree."
            )
        del labeled

        test_recipe = yaml.safe_load(
            (bundle / "test-representation.local.yaml").read_text()
        )
        test = decode_delimited_text(
            bundle / "test-features.csv.gz", test_recipe["options"], compression="gzip"
        )
        with archive.open("GISETTE/gisette_test.data") as stream:
            expected_test = np.loadtxt(stream, dtype=np.int64)
        if (
            expected_test.shape != (6500, 5000)
            or test.data.shape != expected_test.shape
        ):
            raise ValueError("Unexpected unlabeled test dimensions.")
        for index, component in enumerate(test.components):
            if component.name != f"x{index + 1}" or not component.valid.all():
                raise ValueError("Unexpected test feature name or missing value.")
            np.testing.assert_array_equal(component.values, expected_test[:, index])
        test_digest = canonical_sha256(test.components)
        if test_digest != test_recipe["expect"]["verification"][0]["digest"]:
            raise ValueError("Unlabeled test canonical digest differs from its recipe.")
        if reference_sha256(test.components) != test_digest:
            raise ValueError("Test canonical encoders disagree.")
    result = {
        "source_values_and_labels": "exact match across all three splits",
        "canonical_encoders": "native Rust and independent Python agree",
        "labeled_sha256": digest,
        "test_sha256": test_digest,
        "independent_release_attestation": False,
    }
    (bundle / "verification.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print("Verified all 67,500,000 feature values and 7,000 labels without scaling.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    verify(parser.parse_args().bundle)
