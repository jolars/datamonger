"""Prepare BRCA1 regression data directly from the official TCGA Level 3 archive."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zlib
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402

SOURCE_ID = "f0b74706-6b9e-4430-931d-9f233b4ac67c"
SOURCE_URL = f"https://api.gdc.cancer.gov/data/{SOURCE_ID}"
LANDING_PAGE = "https://gdc.cancer.gov/about-data/publications/brca_2012"
SOURCE_SIZE = 78264320
SOURCE_SHA256 = "e49acb5b765d9ada53a713cb95d0a34bcdb60836a1eff2a44d4f0414f4c24af1"
SOURCE_MD5 = "e18990520aef7e2d3a7b8e301f040538"
SOURCE_MD5_URL = "https://api.gdc.cancer.gov/data/4b54d31e-0a64-4a3f-bf4d-e3af1c1e0b6b"
CSV_SHA256 = "27a935c54afc869fe2e7865b0af41d0c640a3223336dcfa497babf53dd392aff"
GZIP_SHA256 = "89c09744bf3229b7cc9c205791e5b4776c4d6b79ef06736e01e1d62eb9c6e012"
CANONICAL_SHA256 = "6eeb45c767fa1dd88bb687d1d25e7a407ba158882c56d11d70d8e3fba0312574"
RIGHTS_URL = "https://gdc.cancer.gov/analyze-data/data-analysis-policies"
REVIEWED_BY = "Codex (automated source review)"
REVIEWED_AT = "2026-10-16"


def sha256(path: Path) -> str:
    """Hash file bytes without retaining another full copy in memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_samples(source: Path, output: Path) -> dict[str, object]:
    """Extract official measurements under validated public sample identifiers."""
    output.mkdir()
    count = 0
    duplicates: list[str] = []
    with tarfile.open(source) as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".tar.gz"):
                continue
            compressed = archive.extractfile(member)
            if compressed is None:
                raise ValueError("Missing TCGA batch archive contents.")
            with compressed, tarfile.open(fileobj=compressed, mode="r|gz") as batch:
                for entry in batch:
                    if not entry.isfile() or not entry.name.endswith(".data.txt"):
                        continue
                    stream = batch.extractfile(entry)
                    if stream is None:
                        raise ValueError("Missing TCGA sample contents.")
                    with stream:
                        contents = stream.read()
                    fields = (
                        contents.split(b"\n", 1)[0]
                        .decode("ascii")
                        .rstrip("\r")
                        .split("\t")
                    )
                    if len(fields) != 2 or fields[0] != "Hybridization REF":
                        raise ValueError("Unexpected TCGA sample header.")
                    sample = fields[1].strip(" ")
                    if re.fullmatch(r"TCGA-[A-Z0-9-]+", sample) is None:
                        raise ValueError("Unexpected TCGA sample identifier.")
                    path = output / f"{sample}.txt"
                    count += 1
                    if path.exists():
                        previous = path.read_bytes()
                        # The duplicate differs only in its sample header spacing.
                        if previous.split(b"\n", 1)[1] != contents.split(b"\n", 1)[1]:
                            raise ValueError(
                                "Duplicate TCGA sample measurements differ."
                            )
                        duplicates.append(sample)
                        if fields[1] != sample:
                            continue
                    path.write_bytes(contents)
    if count != 607 or len(list(output.glob("*.txt"))) != 606 or len(duplicates) != 1:
        raise ValueError("Unexpected TCGA archive inventory.")
    return {
        "sample_files": count,
        "unique_samples": 606,
        "identical_duplicates": duplicates,
    }


def prepare(output: Path, source_path: Path | None = None) -> None:
    """Write and validate a local portable bundle outside the repository."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    source = sources / "BRCA.Gene_Expression.Level_3.tar"
    if source_path is None:
        with urlopen(SOURCE_URL, timeout=60) as response, source.open("wb") as target:
            shutil.copyfileobj(response, target)
    else:
        shutil.copyfile(source_path, source)
    if source.stat().st_size != SOURCE_SIZE or sha256(source) != SOURCE_SHA256:
        raise ValueError("TCGA archive does not match the pinned size and SHA-256.")
    with source.open("rb") as stream:
        if hashlib.file_digest(stream, "md5").hexdigest() != SOURCE_MD5:
            raise ValueError("TCGA archive differs from its published MD5 checksum.")
    samples = sources / "samples"
    inventory = extract_samples(source, samples)

    recipe = Path(__file__).with_name("convert.R")
    preparation = Path(__file__).with_name("read_source.R")
    verifier = Path(__file__).with_name("verify.R")
    data = output / "data.csv.gz"
    with tempfile.TemporaryDirectory(prefix=".conversion-", dir=output) as directory:
        csv_path = Path(directory) / "data.csv"
        subprocess.run(
            ["Rscript", str(recipe), str(samples), str(csv_path), str(preparation)],
            check=True,
        )
        if sha256(csv_path) != CSV_SHA256:
            raise ValueError("Converted CSV differs from the reviewed TCGA bytes.")
        # Omit timestamps and filenames so compression is reproducible.
        with (
            csv_path.open("rb") as stream,
            data.open("wb") as target,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=target, mtime=0, compresslevel=9
            ) as compressed,
        ):
            shutil.copyfileobj(stream, compressed)
    if sha256(data) != GZIP_SHA256:
        raise ValueError("Compressed CSV differs from the reviewed TCGA bytes.")

    with gzip.open(data, "rt", newline="", encoding="utf-8") as stream:
        names = next(csv.reader(stream))
    if names[0] != "sample_id" or names[-1] != "y":
        raise ValueError("Unexpected sample identifier or target column.")
    options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [
            {"name": name, "type": "string" if name == "sample_id" else "float64"}
            for name in names
        ],
    }
    print("Decoding 536 samples and 17,324 columns in Python.", flush=True)
    decoded = decode_delimited_text(data, options, compression="gzip")
    if decoded.data.shape != (536, 17324) or any(
        not component.valid.all() for component in decoded.components
    ):
        raise ValueError("Unexpected decoded dimensions or missing values.")
    expectation = dm_add._expectation(decoded.components)
    if expectation["verification"][0]["digest"] != CANONICAL_SHA256:
        raise ValueError("Decoded values differ from the reviewed canonical digest.")
    artifact = {
        "name": "data",
        "format": "csv",
        "compression": "gzip",
        "size": data.stat().st_size,
        "sha256": GZIP_SHA256,
        "distribution": "metadata-only",
        "downloads": [],
    }
    rights = {
        "status": "known",
        "url": RIGHTS_URL,
        "evidence": (
            "Official TCGA open-access Agilent Level 3 measurements, retrieved "
            "from the NCI GDC publication archive. GDC policies permit analysis "
            "and publication of open-access data, require attribution, and prohibit "
            "attempts to reidentify participants. This automated review treats "
            "publishing the portable numeric extract as publication under those "
            "source policies. No SPDX license or public-domain dedication is "
            "inferred. Iowa's RDS and added annotations are not preparation inputs."
        ),
        "reviewed_by": REVIEWED_BY,
        "reviewed_at": REVIEWED_AT,
    }
    manifest = {
        "schema_version": 1,
        "source": "datamonger",
        "name": "brca1",
        "version": "1",
        "title": "BRCA1 expression in TCGA breast cancer samples",
        "description": (
            "Prepared directly from official TCGA Agilent Level 3 measurements "
            "hosted by the NCI GDC. Contains 533 primary tumors, three metastatic "
            "tumors, 17,322 complete gene expression predictors, and response y "
            "(BRCA1 expression). Values are log2 lowess-normalized Cy5/Cy3 ratios "
            "collapsed by gene symbol. Retains official precision, gene symbols, "
            "and sample identifiers, with no extra centering or imputation. "
            "Samples and predictors are sorted lexicographically. The public "
            "sample_id is metadata excluded from model features. Iowa's added "
            "gene annotations are omitted."
        ),
        "modality": "tabular",
        "provenance": {
            "provider": "Datamonger; derived from official TCGA data at the NCI GDC",
            "upstream_name": "TCGA BRCA Agilent G4502A-07-3 Level 3",
            "upstream_id": SOURCE_ID,
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "landing_page": LANDING_PAGE,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": [
                "The Cancer Genome Atlas Network",
                "University of North Carolina Cancer Genomic Characterization Center",
            ],
            "citation": (
                "The Cancer Genome Atlas Network (2012). Comprehensive molecular "
                "portraits of human breast tumours. Nature 490:61-70. "
                "doi:10.1038/nature11412. Underlying TCGA Level 3 gene expression "
                f"archive at the NCI GDC: {SOURCE_ID}."
            ),
        },
        "license": rights,
        "artifacts": [artifact],
        "representation": {
            "decoder": "delimited-text",
            "decoder_version": 1,
            "inputs": {"data": "data"},
            "options": options,
            "expect": expectation,
        },
        "tasks": [
            {
                "name": "default",
                "type": "regression",
                "features": names[1:-1],
                "target": "y",
            }
        ],
    }
    dm_index.validate_manifest(manifest, root=ROOT)
    subprocess.run(
        [
            "Rscript",
            str(verifier),
            str(ROOT),
            str(samples),
            str(data),
            str(preparation),
            CANONICAL_SHA256,
        ],
        check=True,
    )
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    portable_names = (
        "convert.R",
        "read_source.R",
        "verify.R",
        "prepare.py",
    )
    for name in portable_names:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    provenance = {
        "dataset_id": "datamonger:brca1@1",
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "source_size": SOURCE_SIZE,
        "source_md5": SOURCE_MD5,
        "source_md5_url": SOURCE_MD5_URL,
        "source_acquisition": "download" if source_path is None else "local file",
        "source_inventory": inventory,
        "retrieved_at": manifest["provenance"]["retrieved_at"],
        "environment": {
            "python": sys.version,
            "r": subprocess.check_output(
                ["Rscript", "--version"], text=True, stderr=subprocess.STDOUT
            ).strip(),
            "zlib": zlib.ZLIB_RUNTIME_VERSION,
            "devenv_lock_sha256": sha256(ROOT / "devenv.lock"),
            "uv_lock_sha256": sha256(ROOT / "packages/python/uv.lock"),
        },
        "files": {
            name: {
                "size": (output / name).stat().st_size,
                "sha256": sha256(output / name),
            }
            for name in ("data.csv.gz", *portable_names, "README.md", "LICENSE")
        },
        "representation": {
            "rows": 536,
            "primary_tumors": 533,
            "metastatic_tumors": 3,
            "predictors": 17322,
            "target": "y",
            "metadata_columns": ["sample_id"],
            "missing_values": 0,
            "excluded_incomplete_genes": 491,
            "csv_sha256": CSV_SHA256,
            "verification": expectation["verification"],
        },
        "source_terms": {
            "url": RIGHTS_URL,
            "access_policy_url": (
                "https://gdc.cancer.gov/access-data/data-access-policies"
            ),
            "requirements": ["source attribution", "no participant reidentification"],
            "code_and_documentation_license": "MIT",
        },
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Validated datamonger:brca1@1 from official TCGA data: {output}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    parser.add_argument(
        "--source", type=Path, help="reuse the pinned TCGA Level 3 archive"
    )
    args = parser.parse_args()
    prepare(args.output, args.source)
