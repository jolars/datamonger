"""Prepare Scheetz2006 regression data from the authors' GEO submission."""

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

SOURCE_URL = (
    "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE5nnn/GSE5680/matrix/"
    "GSE5680_series_matrix.txt.gz"
)
SOURCE_SIZE = 29409846
SOURCE_SHA256 = "ff7c8926a30267df8b08d1d1f37b710e81f2e3b115341a4a445b0c02da88edb5"
CSV_SHA256 = "68bf8ac655d98bd42bd7ddaa2b5aa79619ac4a5291c78a151c136eef35061207"
GZIP_SHA256 = "8348d10e5ef29b95c5a9a757e0cee189758364bfae22baef72027a041cf0156e"
CANONICAL_SHA256 = "efcb6e82af27379e0959e5722b2e35a2db08a31a104d329c05da7430c2263b19"
LANDING_PAGE = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE5680"
RIGHTS_URL = "https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(output: Path, source_path: Path | None = None) -> None:
    """Create and validate a local bundle without publishing any files."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    source = sources / "GSE5680_series_matrix.txt.gz"
    if source_path is None:
        with urlopen(SOURCE_URL, timeout=60) as response, source.open("wb") as target:
            shutil.copyfileobj(response, target)
    else:
        shutil.copyfile(source_path, source)
    if source.stat().st_size != SOURCE_SIZE or sha256(source) != SOURCE_SHA256:
        raise ValueError("GEO source differs from the reviewed size and SHA-256.")

    recipe = Path(__file__).with_name("convert.R")
    preparation = Path(__file__).with_name("read_source.R")
    verifier = Path(__file__).with_name("verify.R")
    r_environment = dict(os.environ)
    # Nix R supplies its own libraries; Python's manylinux path breaks R helpers.
    r_environment.pop("LD_LIBRARY_PATH", None)
    data = output / "data.csv.gz"
    with tempfile.TemporaryDirectory(prefix=".conversion-", dir=output) as directory:
        csv_path = Path(directory) / "data.csv"
        subprocess.run(
            ["Rscript", str(recipe), str(source), str(csv_path), str(preparation)],
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
    if (
        len(names) != 18987
        or names[0] != "sample_id"
        or names[-1] != "y"
        or "1389163_at" in names
    ):
        raise ValueError("Unexpected identifier, predictor, or target columns.")
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
    decoded = decode_delimited_text(data, options, compression="gzip")
    if decoded.data.shape != (120, len(names)) or any(
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
            str(source),
            str(data),
            str(preparation),
            digest,
        ],
        check=True,
        env=r_environment,
    )
    artifact = {
        "name": "data",
        "format": "csv",
        "compression": "gzip",
        "size": data.stat().st_size,
        "sha256": sha256(data),
        "distribution": "metadata-only",
        "downloads": [],
    }
    rights = {
        "status": "known",
        "url": RIGHTS_URL,
        "evidence": (
            "GEO places no restrictions on use or distribution of submitted data, "
            "while warning that submitters may retain intellectual property rights. "
            "No additional data-specific restriction was found in GSE5680 or its "
            "sample records. This review treats GEO's source terms as the "
            "redistribution basis for this numeric extract, retaining attribution. "
            "No SPDX license or public-domain dedication is inferred. Iowa's RDS, "
            "code, and added annotations are not preparation inputs."
        ),
        "reviewed_by": "Codex (automated source review)",
        "reviewed_at": "2026-10-16",
    }
    manifest = {
        "schema_version": 3,
        "source": "datamonger",
        "name": "scheetz2006",
        "version": "1",
        "title": "Trim32 expression in rat eye tissue",
        "description": (
            "Prepared from the authors' GSE5680 processed RMA expression matrix. "
            "Contains 120 F2 rats from an SR/JrHsd x SHRSP intercross, with "
            "18,985 expression predictors and response y (Trim32 probe 1389163_at). "
            "Retains GEO numeric precision, sample identifiers, and source sample "
            "and probe order, without additional normalization or imputation. "
            "After excluding 57 AFFX controls, selection keeps probes whose "
            "maximum exceeds the global first quartile and whose range is at "
            "least one on the log2 scale, following the paper's rule at full "
            "precision. This retains 10 predictors beyond Iowa's rounded export. "
            "sample_id is metadata excluded from model features. Added gene "
            "annotations and experimental controls are omitted."
        ),
        "modality": "tabular",
        "preprocessing": dm_index.load_yaml(
            ROOT / "registry/datasets/datamonger/scheetz2006-1.yaml"
        )["preprocessing"],
        "provenance": {
            "provider": "Datamonger; derived from Scheetz et al. at NCBI GEO",
            "upstream_name": "Expression data for an eQTL experiment in rat eye",
            "upstream_id": "GSE5680",
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "landing_page": LANDING_PAGE,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": [
                "Todd E. Scheetz",
                "Kwang-Youn A. Kim",
                "Ruth E. Swiderski",
                "Alisdair R. Philp",
                "Terry A. Braun",
                "Kevin L. Knudtson",
                "Anne M. Dorrance",
                "Gerald F. DiBona",
                "Jian Huang",
                "Thomas L. Casavant",
                "Val C. Sheffield",
                "Edwin M. Stone",
            ],
            "citation": (
                "Scheetz TE, Kim K-YA, Swiderski RE, Philp AR, Braun TA, Knudtson KL, "
                "Dorrance AM, DiBona GF, Huang J, Casavant TL, Sheffield VC, and "
                "Stone EM (2006). Regulation of gene expression in the mammalian eye "
                "and its relevance to eye disease. PNAS 103:14429-14434. "
                "doi:10.1073/pnas.0602562103. GEO accession GSE5680."
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
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    portable_names = ("prepare.py", "read_source.R", "convert.R", "verify.R")
    for name in portable_names:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    provenance = {
        "dataset_id": "datamonger:scheetz2006@1",
        "source_url": SOURCE_URL,
        "source_size": SOURCE_SIZE,
        "source_sha256": SOURCE_SHA256,
        "source_acquisition": "download" if source_path is None else "local file",
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
            "rows": 120,
            "predictors": len(names) - 2,
            "target": {"name": "y", "probe": "1389163_at", "gene": "Trim32"},
            "metadata_columns": ["sample_id"],
            "missing_values": 0,
            "selection": {
                "excluded_control_probes": 57,
                "selection_rounding": "none",
                "expression_threshold": 4.2818075363880554,
                "expression_predicate": "max > threshold",
                "variation_predicate": "max - min >= 1 on the log2 scale",
                "output_rounding": "none",
            },
            "csv_sha256": csv_sha256,
            "verification": expectation["verification"],
        },
        "source_terms": rights,
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Validated datamonger:scheetz2006@1: {decoded.data.shape}, {digest}")
    print(f"Prepared local bundle: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    parser.add_argument("--source", type=Path, help="reuse the pinned GEO source file")
    arguments = parser.parse_args()
    prepare(arguments.output, arguments.source)
