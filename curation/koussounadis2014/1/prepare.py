"""Prepare Koussounadis2014 regression data from the original GEO sources."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
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

SOURCE_ROOT = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE49nnn/GSE49577"
SOURCES = {
    "GSE49577_series_matrix.txt.gz": {
        "url": f"{SOURCE_ROOT}/matrix/GSE49577_series_matrix.txt.gz",
        "size": 25665623,
        "sha256": "f7f81dddb19a9ae306c80a6d930aac47dd20bf42afab42f876629997501d6023",
    },
    "GPL10558.txt": {
        "url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?"
        "acc=GPL10558&targ=self&form=text&view=full",
        "size": 75785789,
        "sha256": "3c7bcae20276e8bf564d9644d6e9a6cb1092c273190284c1e87c92ef023c99a1",
    },
    "GSE49577_phenodata_matrix.txt.gz": {
        "url": f"{SOURCE_ROOT}/suppl/GSE49577_phenodata_matrix.txt.gz",
        "size": 1035,
        "sha256": "867378b8938822ff51506e3e6efd3feb3ce6290c95d38b57001a2d77a9efdd06",
    },
}
CSV_SHA256 = "4eea58215f27cfa4085a1b90ebb57ab71866a0b16fbc9e39d6f211e66b6f20e0"
GZIP_SHA256 = "d532f3aeb8159a7c44ab8e2fc4e4104f923c436a1001eb0c7c2e8abaa02f9c56"
CANONICAL_SHA256 = "59f7c34a97f9368c1947cc8e5339a01e31452f4493911ed1d714aada5fe11e59"
LANDING_PAGE = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE49577"
RIGHTS_URL = "https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html"
METADATA_TYPES = {
    "sample_id": "string",
    "tumor_id": "string",
    "Treatment": "string",
    "Day": "int64",
    "CellLine": "string",
    "RTV": "float64",
}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(output: Path, source_directory: Path | None = None) -> None:
    """Create a verified local bundle without publishing files."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    for name, record in SOURCES.items():
        destination = sources / name
        if source_directory is None:
            with (
                urlopen(str(record["url"]), timeout=60) as response,
                destination.open("wb") as target,
            ):
                shutil.copyfileobj(response, target)
        else:
            shutil.copyfile(source_directory / name, destination)
        if (
            destination.stat().st_size != record["size"]
            or sha256(destination) != record["sha256"]
        ):
            raise ValueError(f"{name} differs from its reviewed size and SHA-256.")

    recipe = Path(__file__).with_name("convert.R")
    preparation = Path(__file__).with_name("read_source.R")
    verifier = Path(__file__).with_name("verify.R")
    source_arguments = [str(sources / name) for name in SOURCES]
    r_environment = dict(os.environ)
    # Nix R supplies its own libraries; Python's manylinux path breaks R helpers.
    r_environment.pop("LD_LIBRARY_PATH", None)
    data = output / "data.csv.gz"
    with tempfile.TemporaryDirectory(prefix=".conversion-", dir=output) as directory:
        csv_path = Path(directory) / "data.csv"
        subprocess.run(
            [
                "Rscript",
                str(recipe),
                *source_arguments,
                str(csv_path),
                str(preparation),
            ],
            check=True,
            env=r_environment,
        )
        csv_sha256 = sha256(csv_path)
        if csv_sha256 != CSV_SHA256:
            raise ValueError("Converted CSV differs from the reviewed GEO extract.")
        # Fixed metadata makes repeated compression produce identical bytes.
        with (
            csv_path.open("rb") as stream,
            data.open("wb") as target,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=target, mtime=0, compresslevel=9
            ) as compressed,
        ):
            shutil.copyfileobj(stream, compressed)
    if sha256(data) != GZIP_SHA256:
        raise ValueError("Compressed CSV differs from the reviewed GEO extract.")

    with gzip.open(data, "rt", newline="", encoding="utf-8") as stream:
        names = next(csv.reader(stream))
    if len(names) != 34701 or names[:6] != list(METADATA_TYPES) or names[-1] != "y":
        raise ValueError("Unexpected metadata, predictor, or target columns.")
    options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [
            {"name": name, "type": METADATA_TYPES.get(name, "float64")}
            for name in names
        ],
    }
    decoded = decode_delimited_text(data, options, compression="gzip")
    if decoded.data.shape != (101, len(names)) or any(
        not component.valid.all() for component in decoded.components
    ):
        raise ValueError("Unexpected decoded dimensions or missing values.")
    expectation = dm_add._expectation(decoded.components)
    digest = expectation["verification"][0]["digest"]
    if digest != CANONICAL_SHA256:
        raise ValueError("Decoded values differ from the reviewed canonical digest.")
    subprocess.run(
        [
            "Rscript",
            str(verifier),
            str(ROOT),
            *source_arguments,
            str(data),
            str(preparation),
            digest,
        ],
        check=True,
        env=r_environment,
    )
    rights = {
        "status": "known",
        "url": RIGHTS_URL,
        "evidence": (
            "GEO places no restrictions on use or distribution of submitted data, "
            "while warning that submitters may retain intellectual property rights. "
            "No additional data-specific restriction was found in GSE49577, "
            "GSM1202097, or GPL10558. This automated review treats GEO's source "
            "terms as the redistribution basis for this numeric extract and its "
            "identifiers, retaining attribution. No SPDX license or public-domain "
            "dedication is inferred. The article's CC BY-NC-SA 3.0 license is not "
            "assumed to license the separate GEO deposit. Iowa's RDS and code "
            "are not preparation inputs."
        ),
        "reviewed_by": "Codex (automated source review)",
        "reviewed_at": "2026-10-19",
    }
    manifest = {
        "schema_version": 3,
        "source": "datamonger",
        "name": "koussounadis2014",
        "version": "1",
        "title": "Gene expression and relative ovarian xenograft tumor volume",
        "description": (
            "Prepared from the authors' GSE49577 processed expression matrix and "
            "phenodata, with GPL10558 internal gene identifiers. Contains 101 "
            "ovarian cancer xenografts, 34,694 expression predictors obtained by "
            "averaging probes with the same ILMN_Gene label, and response y "
            "(log2 relative tumor volume). Preserves GEO sample order and numeric "
            "precision, with labels sorted by ASCII bytes. Retains sample_id, "
            "tumor_id, Treatment, Day, CellLine, and untransformed RTV as metadata "
            "excluded from model features. No additional normalization, filtering, "
            "imputation, or repair of historical gene labels is applied."
        ),
        "modality": "tabular",
        "preprocessing": dm_index.load_yaml(
            ROOT / "registry/datasets/datamonger/koussounadis2014-1.yaml"
        )["preprocessing"],
        "provenance": {
            "provider": "Datamonger; derived from Koussounadis et al. at NCBI GEO",
            "upstream_name": "Chemotherapy induced dynamic gene expression changes "
            "in vivo are prognostic in ovarian cancer",
            "upstream_id": "GSE49577; GPL10558",
            "upstream_version": "Pinned source sizes and SHA-256 digests in "
            "curation/koussounadis2014/1/prepare.py and deposited provenance.json",
            "landing_page": LANDING_PAGE,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": [
                "Antonis Koussounadis",
                "Simon P. Langdon",
                "David J. Harrison",
                "V. Anne Smith",
            ],
            "citation": (
                "Koussounadis A, Langdon SP, Harrison DJ, and Smith VA (2014). "
                "Chemotherapy-induced dynamic gene expression changes in vivo "
                "are prognostic in ovarian cancer. British Journal of Cancer "
                "110:2975-2984. doi:10.1038/bjc.2014.258. GEO accession GSE49577, "
                "platform GPL10558."
            ),
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
                "type": "regression",
                "features": names[6:-1],
                "target": "y",
            }
        ],
    }
    dm_index.validate_manifest(manifest, root=ROOT)
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    portable_names = ("prepare.py", "read_source.R", "convert.R", "verify.R")
    for name in portable_names:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    provenance = {
        "dataset_id": "datamonger:koussounadis2014@1",
        "sources": SOURCES,
        "source_acquisition": "download" if source_directory is None else "local files",
        "retrieved_at": manifest["provenance"]["retrieved_at"],
        "environment": {
            "python": sys.version,
            "r": subprocess.check_output(
                ["Rscript", "--version"],
                text=True,
                stderr=subprocess.STDOUT,
                env=r_environment,
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
            "rows": 101,
            "source_probes": 47323,
            "predictors": 34694,
            "target": {"name": "y", "meaning": "log2(RTV)"},
            "metadata_columns": list(METADATA_TYPES),
            "missing_values": 0,
            "probe_grouping": "mean by GPL10558 ILMN_Gene, ASCII label order",
            "csv_sha256": csv_sha256,
            "verification": expectation["verification"],
        },
        "source_terms": rights,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Validated datamonger:koussounadis2014@1: {decoded.data.shape}, {digest}")
    print(f"Prepared local bundle: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    parser.add_argument(
        "--sources", type=Path, help="directory of pinned GEO source files"
    )
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.sources)
