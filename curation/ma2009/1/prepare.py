"""Stage the pinned UCI URL Reputation release as two Zenodo upload plans."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import shutil
import tarfile
import zipfile
import zlib
from pathlib import Path

SOURCE_DOI = "10.24432/C5H89Q"
SOURCE_SHA256 = "373b33d806a83bab7258b2d3f6ceeffc02f4e1bb98cd17a0d1c938e6156944d1"
ARCHIVE_MEMBER = "url_svmlight.tar.gz"
AUTHORS = ["Ma, Justin", "Saul, Lawrence K.", "Savage, Stefan", "Voelker, Geoffrey M."]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source: Path, output: Path) -> None:
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("The UCI ZIP does not match the pinned SHA-256 digest")

    ranges = (range(61), range(61, 121))
    parts = [output / f"part-{number}" for number in (1, 2)]
    members = {
        f"url_svmlight/Day{day}.svm": part / f"Day{day}.svm.gz"
        for days, part in zip(ranges, parts, strict=True)
        for day in days
    }
    feature_types_member = "url_svmlight/FeatureTypes"
    expected = set(members) | {feature_types_member}
    seen: set[str] = set()
    source_digests: dict[str, str] = {}

    output.mkdir()
    output.chmod(0o755)
    for part in parts:
        part.mkdir()

    with (
        zipfile.ZipFile(source) as bundle,
        bundle.open(ARCHIVE_MEMBER) as archive,
        tarfile.open(fileobj=archive, mode="r|gz") as entries,
    ):
        for entry in entries:
            if entry.name == "url_svmlight" and entry.isdir():
                continue
            if entry.name not in expected or entry.name in seen or not entry.isfile():
                raise ValueError(f"Unexpected archive member: {entry.name}")
            seen.add(entry.name)
            data = entries.extractfile(entry)
            assert data is not None
            with data:
                if entry.name == feature_types_member:
                    feature_types = data.read()
                    source_digests[entry.name] = hashlib.sha256(
                        feature_types
                    ).hexdigest()
                    for part in parts:
                        (part / "FeatureTypes").write_bytes(feature_types)
                    continue

                destination = members[entry.name]
                digest = hashlib.sha256()
                with (
                    destination.open("wb") as target,
                    gzip.GzipFile(
                        filename="", fileobj=target, mode="wb", mtime=0, compresslevel=6
                    ) as compressed,
                ):
                    while chunk := data.read(1024 * 1024):
                        digest.update(chunk)
                        compressed.write(chunk)
                source_digests[entry.name] = digest.hexdigest()
                with gzip.open(destination, "rb") as restored:
                    if (
                        hashlib.file_digest(restored, "sha256").hexdigest()
                        != digest.hexdigest()
                    ):
                        raise ValueError(f"Round-trip mismatch for {entry.name}")

    if seen != expected:
        raise ValueError(f"Missing archive members: {sorted(expected - seen)}")

    documentation = Path(__file__).with_name("DATASET.md")
    for number, (days, part) in enumerate(zip(ranges, parts, strict=True), start=1):
        first, last = days[0], days[-1]
        shutil.copyfile(documentation, part / "README.md")
        with (part / "README.md").open("a", encoding="utf-8") as readme:
            readme.write(
                f"\n## Files in this record\n\n"
                f"- `Day{first}.svm.gz` through `Day{last}.svm.gz` contain the "
                f"{len(days)} consecutive day files in part {number} of 2.\n"
                "- `FeatureTypes` lists the indices of real-valued features.\n"
                "- `SHA256SUMS` lists the digests of the data files and this README.\n"
            )
        files = [f"Day{day}.svm.gz" for day in days] + ["FeatureTypes", "README.md"]
        (part / "SHA256SUMS").write_text(
            "".join(f"{sha256(part / name)}  {name}\n" for name in files),
            encoding="utf-8",
        )
        plan = {
            "metadata": {
                "title": (
                    f"URL Reputation (UCI), part {number} of 2, days {first}-{last}"
                ),
                "upload_type": "dataset",
                "description": (
                    f"<p>Days {first}-{last} of the UCI URL Reputation dataset. "
                    "Each SVM-light file is individually gzip-compressed. "
                    "Day membership, row order, feature values, and labels "
                    "are preserved. "
                    "Positive labels indicate malicious URLs and negative labels "
                    "indicate benign URLs.</p>"
                    f'<p>Derived from the <a href="https://doi.org/{SOURCE_DOI}">'
                    "UCI deposit</a> by Ma, Saul, Savage, and Voelker.</p>"
                ),
                "creators": [{"name": name} for name in AUTHORS],
                "access_right": "open",
                "license": "cc-by-4.0",
                "version": "1",
                "related_identifiers": [
                    {
                        "identifier": SOURCE_DOI,
                        "relation": "isDerivedFrom",
                        "resource_type": "dataset",
                        "scheme": "doi",
                    },
                ],
            },
            "files": [*files, "SHA256SUMS"],
        }
        (part / "deposit.json").write_text(
            json.dumps(plan, indent=2) + "\n", encoding="utf-8"
        )

    manifest = {
        "source_sha256": SOURCE_SHA256,
        "source_member_sha256": source_digests,
        "python": platform.python_version(),
        "zlib": zlib.ZLIB_RUNTIME_VERSION,
    }
    (output / "preparation.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Pinned UCI ZIP archive")
    parser.add_argument("output", type=Path, help="New staging directory")
    args = parser.parse_args()
    prepare(args.source, args.output)
