from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "dm_catalog", ROOT / "tools/dm_catalog.py"
)
assert SPEC is not None and SPEC.loader is not None
dm_catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_catalog)


def write_snapshot(root: Path, index: dict[str, Any]) -> None:
    directory = root / "registry/releases/1.2.0"
    directory.mkdir(parents=True, exist_ok=True)
    data = json.dumps(index).encode()
    (directory / "index.json").write_bytes(data)
    selector = root / dm_catalog.DEFAULT_SELECTOR
    selector.parent.mkdir(parents=True, exist_ok=True)
    selector.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release": "1.2.0",
                "index_sha256": hashlib.sha256(data).hexdigest(),
                "index_url": "https://github.com/jolars/datamonger/releases/download/registry-v1.2.0/index.json",
            }
        )
    )


def read_index(root: Path) -> dict[str, Any]:
    return json.loads((root / "registry/releases/1.2.0/index.json").read_bytes())


@pytest.fixture
def catalog_root(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "spec/schema", tmp_path / "spec/schema")
    index = json.loads((ROOT / "registry/releases/1.2.0/index.json").read_bytes())
    names = {
        "iris",
        "wholesale-customers",
        "dna_scale",
        "breast-cancer-wisconsin-diagnostic",
    }
    index["datasets"] = [
        record for record in index["datasets"] if record["name"] in names
    ]
    index["defaults"] = [
        record for record in index["defaults"] if record["name"] in names
    ]
    write_snapshot(tmp_path, index)
    return tmp_path


def test_counts_follow_tasks_and_splits(catalog_root: Path) -> None:
    outputs = dm_catalog.generate(catalog_root)
    catalog = json.loads(outputs[Path("catalog.json")])
    entries = {entry["name"]: entry for entry in catalog["datasets"]}
    assert entries["iris"]["dimensions"] == [
        {
            "task": "default",
            "type": "classification",
            "split": None,
            "samples": 150,
            "predictors": 4,
        }
    ]
    assert (
        entries["breast-cancer-wisconsin-diagnostic"]["dimensions"][0]["predictors"]
        == 30
    )
    assert entries["dna_scale"]["dimensions"] == [
        {
            "task": "default",
            "type": "classification",
            "split": "test",
            "samples": 1186,
            "predictors": 180,
        },
        {
            "task": "default",
            "type": "classification",
            "split": "train",
            "samples": 2000,
            "predictors": 180,
        },
    ]
    assert entries["dna_scale"]["storage"] == "sparse"
    assert entries["wholesale-customers"]["tasks"] == []
    assert entries["wholesale-customers"]["dimensions"] == [
        {"task": None, "type": None, "split": None, "samples": 440, "predictors": None}
    ]
    page = outputs[Path("libsvm/dna_scale/1.md")].decode()
    assert "| default | classification | test | 1,186 | 180 |" in page
    assert "| default | classification | train | 2,000 | 180 |" in page


def test_uses_bundled_snapshot_and_keeps_search_projection_small(
    catalog_root: Path,
) -> None:
    (catalog_root / "registry/latest.json").write_text('{"release":"unpublished"}')
    authored = catalog_root / "registry/datasets/uci/unreleased.yaml"
    authored.parent.mkdir(parents=True)
    authored.write_text("This must not be read by the website.")
    outputs = dm_catalog.generate(catalog_root)
    catalog = json.loads(outputs[Path("catalog.json")])
    assert catalog["registry"]["release"] == "1.2.0"
    assert len(catalog["datasets"]) == 4
    assert len(outputs[Path("catalog.json")]) < 10_000
    assert "representation" not in catalog["datasets"][0]
    assert outputs == dm_catalog.generate(catalog_root)


@pytest.mark.parametrize("schema_version", [4, 5])
@pytest.mark.parametrize("name", ["iris", "dna_scale"])
def test_feature_only_split_counts(
    catalog_root: Path, name: str, schema_version: int
) -> None:
    index = read_index(catalog_root)
    index["schema_version"] = schema_version
    dataset = next(d for d in index["datasets"] if d["name"] == name)
    dataset["schema_version"] = schema_version
    task = dataset["tasks"][0]
    if name == "iris":
        roles = {key: task.pop(key) for key in ("features", "target")}
        task["splits"] = {"train": roles, "test": copy.deepcopy(roles)}
    del task["splits"]["test"]["target"]
    write_snapshot(catalog_root, index)

    outputs = dm_catalog.generate(catalog_root)
    entry = next(
        e
        for e in json.loads(outputs[Path("catalog.json")])["datasets"]
        if e["name"] == name
    )
    samples, predictors = (150, 4) if name == "iris" else (1186, 180)
    assert entry["dimensions"][0] == {
        "task": "default",
        "type": "classification",
        "split": "test",
        "samples": samples,
        "predictors": predictors,
    }
    page = outputs[Path(dataset["source"]) / name / "1.md"].decode()
    assert f"| default | classification | test | {samples:,} | {predictors} |" in page


@pytest.mark.parametrize("split", [False, True])
def test_target_only_task_counts(catalog_root: Path, split: bool) -> None:
    index = read_index(catalog_root)
    dataset = next(d for d in index["datasets"] if d["name"] == "iris")
    task = dataset["tasks"][0]
    del task["features"]
    if split:
        task["splits"] = {"test": {"target": task.pop("target")}}
    write_snapshot(catalog_root, index)

    outputs = dm_catalog.generate(catalog_root)
    entry = next(
        e
        for e in json.loads(outputs[Path("catalog.json")])["datasets"]
        if e["name"] == "iris"
    )
    assert entry["dimensions"] == [
        {
            "task": "default",
            "type": "classification",
            "split": "test" if split else None,
            "samples": 150,
            "predictors": None,
        }
    ]
    assert "| 150 | Unknown |" in outputs[Path("uci/iris/1.md")].decode()


@pytest.mark.parametrize("name", ["iris", "dna_scale"])
def test_unsupervised_task_counts(catalog_root: Path, name: str) -> None:
    index = read_index(catalog_root)
    dataset = next(d for d in index["datasets"] if d["name"] == name)
    expected = dm_catalog.dimensions(dataset)
    task = dataset["tasks"][0]
    task["type"] = "unsupervised"
    for binding in task.get("splits", {"": task}).values():
        del binding["target"]
    write_snapshot(catalog_root, index)

    outputs = dm_catalog.generate(catalog_root)
    entry = next(
        e
        for e in json.loads(outputs[Path("catalog.json")])["datasets"]
        if e["name"] == name
    )
    assert entry["tasks"] == ["unsupervised"]
    assert entry["dimensions"] == [
        {**dimension, "type": "unsupervised"} for dimension in expected
    ]


def test_declared_defaults_take_precedence_over_version_sorting(
    catalog_root: Path,
) -> None:
    index = read_index(catalog_root)
    other = copy.deepcopy(next(d for d in index["datasets"] if d["name"] == "iris"))
    other["version"] = "10+revision"
    index["datasets"].append(other)
    write_snapshot(catalog_root, index)
    outputs = dm_catalog.generate(catalog_root)
    versions = [
        entry
        for entry in json.loads(outputs[Path("catalog.json")])["datasets"]
        if entry["name"] == "iris"
    ]
    assert [(entry["version"], entry["default"]) for entry in versions] == [
        ("1", True),
        ("10+revision", False),
    ]
    assert versions[1]["url"] == "/datasets/uci/iris/10%2Brevision"
    browser = outputs[Path("index.md")].decode()
    assert "uci/iris/1.md" in browser
    assert "10%2Brevision" not in browser
    assert "10%2Brevision.md" in outputs[Path("uci/iris/1.md")].decode()
    assert Path("uci/iris/10+revision.md") in outputs


@pytest.mark.parametrize("schema_version", [1, 2, 3])
def test_supported_schemas_and_pinned_retrieval(
    catalog_root: Path, schema_version: int
) -> None:
    index = read_index(catalog_root)
    index["schema_version"] = schema_version
    iris = next(d for d in index["datasets"] if d["name"] == "iris")
    iris["schema_version"] = schema_version
    if schema_version >= 2:
        iris["provenance"]["citations"] = [
            {"citation": "A dataset reference.", "recommended": True}
        ]
    if schema_version == 3:
        iris["preprocessing"] = {
            "upstream": {"status": "unknown", "notes": "History not established."},
            "datamonger": {
                "status": "documented",
                "steps": [
                    {"kind": "scaling", "description": "Scale the measurements."}
                ],
                "evidence": ["https://example.org/preparation"],
            },
        }
    write_snapshot(catalog_root, index)
    outputs = dm_catalog.generate(catalog_root)
    selector = json.loads(outputs[Path("selector.json")])
    page = outputs[Path("uci/iris/1.md")].decode()
    assert page.count(selector["index_sha256"]) == 5
    for language in ("python", "r", "julia", "sh"):
        assert f"```{language}\n" in page
    assert page.count("uci:iris@1") == 5
    assert json.loads(outputs[Path("uci/iris/1.json")]) == iris
    if schema_version == 1:
        assert "Preprocessing history is not recorded" in page
    else:
        assert "Recommended citation. A dataset reference." in page
    if schema_version == 3:
        assert "History not established." in page
        assert "Scale the measurements." in page


def test_bad_digest_leaves_existing_output_untouched(catalog_root: Path) -> None:
    outputs = dm_catalog.generate(catalog_root)
    index = catalog_root / "registry/releases/1.2.0/index.json"
    index.write_bytes(index.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest"):
        dm_catalog.generate(catalog_root)
    for path, contents in outputs.items():
        assert (
            catalog_root / dm_catalog.DEFAULT_OUTPUT / path
        ).read_bytes() == contents


@pytest.mark.parametrize(
    "failure", ["schema", "release", "duplicate", "default", "path"]
)
def test_invalid_snapshots_are_rejected(catalog_root: Path, failure: str) -> None:
    index = read_index(catalog_root)
    if failure == "schema":
        index["schema_version"] = 99
    elif failure == "release":
        index["release"] = "other"
    elif failure == "duplicate":
        index["datasets"].append(copy.deepcopy(index["datasets"][0]))
    elif failure == "default":
        index["defaults"][0]["version"] = "missing"
    else:
        index["datasets"][0]["version"] = "../escape"
    write_snapshot(catalog_root, index)
    with pytest.raises((ValueError, ValidationError)):
        dm_catalog.generate(catalog_root)
    assert not (catalog_root / dm_catalog.DEFAULT_OUTPUT).exists()


def test_wide_records_remain_complete_and_metadata_is_escaped(
    catalog_root: Path,
) -> None:
    index = read_index(catalog_root)
    iris = next(d for d in index["datasets"] if d["name"] == "iris")
    iris["title"] = "A | <script>alert(1)</script> [title]"
    iris["provenance"]["citation"] = "A reference. doi:10.1234/example."
    iris["license"] = {"status": "unknown", "url": "https://example.org/terms"}
    iris["representation"]["expect"]["components"].extend(
        {"name": f"extra_{number}", "kind": "vector", "type": "float64", "length": 150}
        for number in range(40)
    )
    write_snapshot(catalog_root, index)
    outputs = dm_catalog.generate(catalog_root)
    page = outputs[Path("uci/iris/1.md")].decode()
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "A \\|" in page
    assert "](<https://doi.org/10.1234/example>)." in page
    assert "Showing 30 of 45 components" in page
    assert "extra_39" not in page
    assert (
        len(
            json.loads(outputs[Path("uci/iris/1.json")])["representation"]["expect"][
                "components"
            ]
        )
        == 45
    )
    entry = next(
        e
        for e in json.loads(outputs[Path("catalog.json")])["datasets"]
        if e["name"] == "iris"
    )
    assert entry["license"] == "Unknown"


def test_prose_links_preserve_url_fragments_and_escape_markdown(
    catalog_root: Path,
) -> None:
    index = read_index(catalog_root)
    index["schema_version"] = 3
    iris = next(d for d in index["datasets"] if d["name"] == "iris")
    iris["schema_version"] = 3
    url = "https://example.org/data_set.html#reference"
    prose = f"A | <script>reference</script>: {url}. doi:10.1234/example."
    iris["description"] = prose
    iris["provenance"].pop("citation", None)
    iris["provenance"]["citations"] = [{"citation": prose, "note": prose}]
    iris["provenance"]["citation_instructions"] = prose
    iris["license"]["evidence"] = prose
    iris["preprocessing"] = {
        "upstream": {"status": "unknown", "notes": prose},
        "datamonger": {
            "status": "documented",
            "steps": [{"kind": "other", "description": prose}],
            "evidence": ["https://example.org/preparation"],
        },
    }
    write_snapshot(catalog_root, index)

    outputs = dm_catalog.generate(catalog_root)
    page = outputs[Path("uci/iris/1.md")].decode()
    assert page.count(f"](<{url}>).") == 7
    assert page.count("](<https://doi.org/10.1234/example>).") == 7
    assert page.count("A \\| &lt;script&gt;reference&lt;/script&gt;:") == 7
    entry = next(
        e
        for e in json.loads(outputs[Path("catalog.json")])["datasets"]
        if e["name"] == "iris"
    )
    assert entry["description"] == prose


def test_removes_only_previously_generated_files(catalog_root: Path) -> None:
    dm_catalog.generate(catalog_root)
    output = catalog_root / dm_catalog.DEFAULT_OUTPUT
    authored = output / "notes.md"
    authored.write_text("Retain this file.")
    index = read_index(catalog_root)
    index["datasets"] = [d for d in index["datasets"] if d["name"] != "iris"]
    index["defaults"] = [d for d in index["defaults"] if d["name"] != "iris"]
    write_snapshot(catalog_root, index)
    dm_catalog.generate(catalog_root)
    assert not (output / "uci/iris/1.md").exists()
    assert not (output / "uci/iris/1.json").exists()
    assert authored.read_text() == "Retain this file."
