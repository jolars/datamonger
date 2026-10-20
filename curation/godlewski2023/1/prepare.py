"""Preserve Godlewski et al.'s complete supplementary metabolomics table as CSV."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import shutil
import sys
import zlib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen
from xml.etree import ElementTree
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402

SOURCE_URL = (
    "https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-023-38243-1/"
    "MediaObjects/41598_2023_38243_MOESM2_ESM.xlsx"
)
SOURCE_SIZE = 226198
SOURCE_SHA256 = "8b532fe953400725c5e5e13541adf984652954ff7ee8c71618381eddd9ada717"
CSV_SHA256 = "e99e1e9d7454e030f659ae60a5b0bdd2b8a39625b739b2727a56ac2061f5cd90"
GZIP_SHA256 = "1e65240b2b258bf32f85eac48518bea57e6579ebce3911daec783e07c38ecfcb"
CANONICAL_SHA256 = "f487f2465c157a250795bdcea53ac3bb935e4b8a41d93a8f3fd7d5286294f287"
PAPER_URL = "https://www.nature.com/articles/s41598-023-38243-1"
ARTICLE_URL = "https://pmc.ncbi.nlm.nih.gov/articles/PMC10329700/"
LABELS = {
    "Glioma grade 1": 3,
    "Glioma grade 2": 15,
    "Glioma grade 3": 10,
    "Glioma grade 4": 66,
    "Meningioma": 70,
    "Healthy control": 71,
}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def read_source(path: Path) -> list[list[str]]:
    """Read the pinned rectangular sheet, preserving its numeric XML tokens."""
    if path.stat().st_size != SOURCE_SIZE or sha256(path) != SOURCE_SHA256:
        raise ValueError("Source differs from its reviewed size and SHA-256.")
    with ZipFile(path) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.findall("m:sheets/m:sheet", NS)
        if len(sheets) != 1 or sheets[0].get("name") != "Sheet1":
            raise ValueError("Expected the single source sheet Sheet1.")
        strings = [
            "".join(node.itertext())
            for node in ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        ]
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row_index, row in enumerate(sheet.findall("m:sheetData/m:row", NS), 1):
        values = []
        if row.get("r") != str(row_index) or len(row) != 140:
            raise ValueError("Unexpected source row coordinates or width.")
        for index, cell in enumerate(row, 1):
            if cell.get("r") != f"{column_letter(index)}{row_index}":
                raise ValueError("Unexpected source cell coordinates.")
            if cell.find("m:f", NS) is not None:
                raise ValueError("The reviewed table should not contain formulas.")
            value = cell.findtext("m:v", None, NS)
            expected_type = "s" if row_index == 1 or index == 2 else None
            if value is None or cell.get("t") != expected_type:
                raise ValueError("Unexpected source cell type or missing value.")
            values.append(strings[int(value)] if expected_type == "s" else value)
        rows.append(values)
    if len(rows) != 236 or len(set(rows[0])) != 140:
        raise ValueError("Unexpected source dimensions or duplicate column names.")
    if rows[0][:2] != ["Sample Name", "Sample type"]:
        raise ValueError("Unexpected sample identifier or label names.")
    if [r[0] for r in rows[1:]] != [str(i) for i in range(1, 236)]:
        raise ValueError("Unexpected source identifiers or row order.")
    if Counter(r[1] for r in rows[1:]) != LABELS:
        raise ValueError("Unexpected source label counts.")
    return rows


def prepare(output: Path, source: Path | None = None) -> None:
    """Create a local bundle without uploading or publishing files."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    workbook = sources / "41598_2023_38243_MOESM2_ESM.xlsx"
    if source is None:
        with urlopen(SOURCE_URL, timeout=60) as response, workbook.open("wb") as target:
            shutil.copyfileobj(response, target)
    else:
        shutil.copyfile(source, workbook)
    rows = read_source(workbook)
    data = output / "data.csv.gz"
    csv_path = output / "data.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)
    csv_digest = sha256(csv_path)
    if csv_digest != CSV_SHA256:
        raise ValueError("Converted CSV differs from the reviewed source extract.")
    # Fixed metadata makes repeated compression produce identical bytes.
    with (
        csv_path.open("rb") as stream,
        data.open("wb") as target,
        gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed,
    ):
        shutil.copyfileobj(stream, compressed)
    if sha256(data) != GZIP_SHA256:
        raise ValueError("Compressed CSV differs from the reviewed artifact.")
    csv_path.unlink()
    names = rows[0]
    options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [
            {
                "name": name,
                "type": "int64" if i == 0 else "string" if i == 1 else "float64",
            }
            for i, name in enumerate(names)
        ],
    }
    decoded = decode_delimited_text(data, options, compression="gzip")
    if decoded.data.shape != (235, 140) or any(
        not component.valid.all() for component in decoded.components
    ):
        raise ValueError("Unexpected decoded dimensions or missing values.")
    expectation = dm_add._expectation(decoded.components)
    if expectation["verification"][0]["digest"] != CANONICAL_SHA256:
        raise ValueError("Decoded values differ from the reviewed canonical digest.")
    rights = {
        "status": "known",
        "identifier": "CC-BY-4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "evidence": (
            "The article licenses its material under CC BY 4.0, subject to "
            "separately credited third-party material. Its data-availability "
            "statement identifies the supplements as part of the work. No "
            "separate restriction or third-party credit appears in Table S2. "
            "This automated source review applies the article license to that "
            "table and its lossless CSV conversion, retaining attribution and "
            "documenting the format change. See curation/godlewski2023/1/RIGHTS.md."
        ),
        "reviewed_by": "Codex (automated source review)",
        "reviewed_at": "2026-10-20",
    }
    manifest = {
        "schema_version": 3,
        "source": "datamonger",
        "name": "godlewski2023",
        "version": "1",
        "title": "Brain tumor plasma metabolomics (Godlewski et al., 2023)",
        "description": (
            "Lossless CSV conversion of complete Supplementary Table S2: 235 "
            "plasma samples, 138 metabolite measurements, Sample Name identifiers, "
            "and the original six Sample type labels (glioma grades 1-4, "
            "meningioma, and healthy control). Preserves every source value, "
            "column name, and row and column order. Identifiers are excluded "
            "from model features. Contains 94 glioma samples although the paper "
            "reports 95. No SLOPE sample selection or binary label mapping is "
            "applied. The study authors normalized, filtered, and imputed the "
            "measurements before publishing the table."
        ),
        "modality": "tabular",
        "preprocessing": {
            "upstream": {
                "status": "documented",
                "evidence": [ARTICLE_URL, PAPER_URL],
                "steps": [
                    {
                        "kind": "normalization",
                        "description": "Authors processed, quantified, and normalized "
                        "the spectra in MetIDQ according to the Biocrates kit manual.",
                        "parameters": {"software": "MetIDQ Oxygen DB110-3005"},
                    },
                    {
                        "kind": "missing-value-removal",
                        "description": "Authors retained metabolites present in at "
                        "least 80% of samples, yielding 138 of 188 measured "
                        "metabolites.",
                        "parameters": {"axis": "columns", "minimum_presence": "80%"},
                    },
                    {
                        "kind": "imputation",
                        "description": "Authors substituted missing measurements "
                        "with half the metabolite's limit of detection in each batch.",
                        "parameters": {"method": "half limit of detection per batch"},
                    },
                ],
                "notes": "The table is processed metabolomics data, not raw spectra. "
                "The paper describes further model-specific processing for its "
                "experiments; those operations are not reproduced here.",
            },
            "datamonger": {
                "status": "none",
                "evidence": [
                    "curation/godlewski2023/1/prepare.py",
                    "curation/godlewski2023/1/DATASET.md",
                ],
                "notes": "Only lossless XLSX-to-CSV conversion and gzip compression. "
                "Retains all samples, original labels, identifiers, measurements, "
                "names, and ordering; no statistical transformations are applied.",
            },
        },
        "provenance": {
            "provider": "Datamonger; derived from Godlewski et al., Scientific Reports",
            "upstream_name": "Supplementary Table S2",
            "upstream_id": "10.1038/s41598-023-38243-1; Table S2",
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "landing_page": PAPER_URL,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": [
                "Adrian Godlewski",
                "Marcin Czajkowski",
                "Patrycja Mojsak",
                "Tomasz Pienkowski",
                "Wioleta Gosk",
                "Tomasz Lyson",
                "Zenon Mariak",
                "Joanna Reszec",
                "Marcin Kondraciuk",
                "Karol Kaminski",
                "Marek Kretowski",
                "Marcin Moniuszko",
                "Adam Kretowski",
                "Michal Ciborowski",
            ],
            "citation": "Godlewski A et al. (2023). A comparison of different "
            "machine-learning techniques for the selection of a panel of metabolites "
            "allowing early detection of brain tumors. Scientific Reports 13:11044. "
            "doi:10.1038/s41598-023-38243-1. Supplementary Table S2.",
        },
        "license": rights,
        "artifacts": [
            {
                "name": "data",
                "format": "csv",
                "compression": "gzip",
                "size": data.stat().st_size,
                "sha256": sha256(data),
                "distribution": "metadata-only",
                "downloads": [],
            }
        ],
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
                "type": "classification",
                "features": names[2:],
                "target": "Sample type",
            }
        ],
    }
    dm_index.validate_manifest(manifest, root=ROOT)
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    portable_names = ("prepare.py", "verify.py", "verify.R")
    for name in portable_names:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    provenance = {
        "dataset_id": "datamonger:godlewski2023@1",
        "retrieved_at": manifest["provenance"]["retrieved_at"],
        "source": {"url": SOURCE_URL, "size": SOURCE_SIZE, "sha256": SOURCE_SHA256},
        "source_acquisition": "download" if source is None else "local file",
        "environment": {
            "python": platform.python_version(),
            "zlib": zlib.ZLIB_RUNTIME_VERSION,
            "devenv_lock_sha256": sha256(ROOT / "devenv.lock"),
            "uv_lock_sha256": sha256(ROOT / "packages/python/uv.lock"),
        },
        "representation": {
            "rows": 235,
            "predictors": 138,
            "columns": 140,
            "missing_values": 0,
            "target": "Sample type",
            "metadata_columns": ["Sample Name"],
            "labels": LABELS,
            "csv_sha256": csv_digest,
            "verification": expectation["verification"],
        },
        "files": {
            name: {
                "size": (output / name).stat().st_size,
                "sha256": sha256(output / name),
            }
            for name in ("data.csv.gz", *portable_names, "README.md", "LICENSE")
        },
        "source_terms": rights,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Validated datamonger:godlewski2023@1: {decoded.data.shape}")
    print(f"Canonical SHA-256: {expectation['verification'][0]['digest']}")
    print(f"CSV SHA-256: {csv_digest}; gzip SHA-256: {sha256(data)}")
    print(f"Prepared local bundle: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    parser.add_argument("--source", type=Path, help="reuse the pinned source workbook")
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.source)
