"""Prepare and validate the Rhee2006 dataset from Stanford HIVDB."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import dm_add  # noqa: E402
import dm_index  # noqa: E402

from datamonger._decode import decode_delimited_text  # noqa: E402

SOURCE_SHA256 = "b89d2ad33300c0e936cb44292e1aee90644a047cb82a6a29fdca14e9d97af8ef"
CSV_SHA256 = "893a104177f8d946fcd7ff429406757aa0d24be890982f0a7ee9cb9540ae00d3"
SOURCE_URL = (
    "https://hivdb.stanford.edu/_wrapper/pages/published_analysis/"
    "genophenoPNAS2006/DATA/PI_DATA.txt"
)
LANDING_PAGE = (
    "https://hivdb.stanford.edu/_wrapper/pages/published_analysis/genophenoPNAS2006/"
)
PREPARATION_REFERENCE = (
    "https://github.com/IowaBiostat/data-sets/blob/"
    "f6b782b919a76898dbc1f0421e96274ef6987b6d/Rhee2006/data.R"
)


def prepare(output: Path) -> None:
    """Write a reproducible local bundle outside the repository."""
    output = output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep generated artifacts outside the repository.")
    output.mkdir(parents=True, exist_ok=False)
    source = output / "PI_DATA.txt"
    with urlopen(SOURCE_URL, timeout=60) as response:
        contents = response.read()
    if len(contents) != 212774 or hashlib.sha256(contents).hexdigest() != SOURCE_SHA256:
        raise ValueError("Stanford source does not match the pinned size and digest.")
    source.write_bytes(contents)
    recipe = Path(__file__).with_name("convert.R")
    shutil.copyfile(recipe, output / "convert.R")
    preparation = Path(__file__).with_name("read_source.R")
    shutil.copyfile(preparation, output / "read_source.R")
    data = output / "data.csv"
    subprocess.run(
        ["Rscript", str(recipe), str(source), str(data), str(preparation)], check=True
    )
    if hashlib.sha256(data.read_bytes()).hexdigest() != CSV_SHA256:
        raise ValueError("Converted CSV differs from the reviewed pilot bytes.")
    with data.open(newline="", encoding="utf-8") as stream:
        names = next(csv.reader(stream))
    options = {
        "encoding": "utf-8",
        "delimiter": ",",
        "header": True,
        "quote": '"',
        "escape": "double",
        "row_order": "source",
        "missing_values": [],
        "columns": [{"name": name, "type": "float64"} for name in names],
    }
    artifact = {
        "name": "data",
        "format": "csv",
        "compression": "none",
        "size": data.stat().st_size,
        "sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "distribution": "metadata-only",
        "downloads": [],
    }
    decoded = decode_delimited_text(data, options)
    manifest = {
        "schema_version": 1,
        "source": "datamonger",
        "name": "rhee2006",
        "version": "1",
        "title": "Rhee2006: HIV drug resistance mutations",
        "description": (
            "Datamonger Nelfinavir dataset prepared directly from Stanford HIVDB's "
            "PI_DATA.txt following Iowa Biostatistics' preparation. Contains 842 "
            "observations and 361 mutation indicators in source row order. "
            "The response y is the natural logarithm of NFV susceptibility. "
            "Identifiers and other drug responses are excluded."
        ),
        "modality": "tabular",
        "provenance": {
            "provider": "Datamonger; derived from Stanford HIVDB",
            "upstream_name": "Rhee2006",
            "upstream_version": f"sha256:{SOURCE_SHA256}",
            "landing_page": LANDING_PAGE,
            "retrieved_at": datetime.now(UTC).date().isoformat(),
            "authors": [
                "Rhee S-Y",
                "Taylor J",
                "Wadhera G",
                "Ben-Hur A",
                "Brutlag DL",
                "Shafer RW",
            ],
            "citation": (
                "Rhee et al. (2006). Genotypic predictors of human immunodeficiency "
                "virus type 1 drug resistance. PNAS 103:17355-17360."
            ),
        },
        "license": {
            "status": "known",
            "url": "https://hivdb.stanford.edu/_wrapper/pages/FAQ/FAQ.html",
            "evidence": (
                "Stanford HIVDB's FAQ describes published data as belonging in the "
                "public domain so others can verify and build on results. "
                "Johan Larsson reviewed this statement and accepted it as covering "
                "redistribution of this dataset. The recorded basis is Stanford's "
                "public-domain statement, not a CC0 dedication or the code MIT license."
            ),
            "reviewed_by": "Johan Larsson",
            "reviewed_at": "2026-10-15",
        },
        "artifacts": [artifact],
        "representation": {
            "decoder": "delimited-text",
            "decoder_version": 1,
            "inputs": {"data": "data"},
            "options": options,
            "expect": dm_add._expectation(decoded.components),
        },
        "tasks": [
            {
                "name": "default",
                "type": "regression",
                "target": "y",
                "features": names[:-1],
            }
        ],
    }
    dm_index.validate_manifest(manifest, root=ROOT)
    subprocess.run(
        [
            "Rscript",
            str(Path(__file__).with_name("verify.R")),
            str(ROOT),
            str(output),
            manifest["representation"]["expect"]["verification"][0]["digest"],
        ],
        check=True,
    )
    (output / "manifest.local.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    provenance = {
        "dataset_id": "datamonger:rhee2006@1",
        "source_url": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "source_size": len(contents),
        "preparation_reference": PREPARATION_REFERENCE,
        "preparation_sha256": hashlib.sha256(preparation.read_bytes()).hexdigest(),
        "recipe_sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
        "r_version": subprocess.check_output(
            ["Rscript", "--version"], text=True, stderr=subprocess.STDOUT
        ).strip(),
        "artifact": {
            key: value
            for key, value in artifact.items()
            if key not in {"distribution", "downloads"}
        },
        "verification": manifest["representation"]["expect"]["verification"],
        "rights_review": manifest["license"],
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    shutil.copyfile(Path(__file__).with_name("DATASET.md"), output / "README.md")
    shutil.copyfile(Path(__file__).with_name("RIGHTS.md"), output / "RIGHTS.md")
    print(f"Validated {len(decoded.components)} columns, 842 rows: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output", type=Path, help="new directory outside the repository"
    )
    prepare(parser.parse_args().output)
