from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "dm_bundle_registry", ROOT / "tools/dm_bundle_registry.py"
)
assert SPEC is not None and SPEC.loader is not None
dm_bundle_registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_bundle_registry)


@pytest.fixture
def bundle_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for path in (
        "registry/releases/1.1.0",
        "spec/schema",
        *map(str, dm_bundle_registry.BUNDLE_DIRECTORIES),
    ):
        shutil.copytree(ROOT / path, tmp_path / path)
    for path in (
        "README.md",
        "packages/python/src/datamonger/_registry.py",
        "packages/r/R/registry.R",
        "packages/julia/src/registry.jl",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    # Keep the baseline fixed when an automation PR updates the real client bundles.
    baseline = tmp_path / "registry/releases/1.1.0"
    (tmp_path / dm_bundle_registry.BUNDLE_DIRECTORIES[0] / "selector.json").write_bytes(
        (baseline / "selector.json").read_bytes()
    )
    monkeypatch.setattr(
        dm_bundle_registry,
        "fetch_index",
        lambda url: (baseline / "index.json").read_bytes(),
    )
    dm_bundle_registry.bundle(tmp_path, "1.1.0")
    directory = tmp_path / "registry/releases/1.2.0"
    directory.mkdir()
    index = json.loads((tmp_path / "registry/releases/1.1.0/index.json").read_bytes())
    index["release"] = "1.2.0"
    contents = json.dumps(index).encode()
    (directory / "index.json").write_bytes(contents)
    (directory / "selector.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release": "1.2.0",
                "index_sha256": hashlib.sha256(contents).hexdigest(),
                "index_url": "https://github.com/jolars/datamonger/releases/download/registry-v1.2.0/index.json",
            }
        )
        + "\n"
    )
    return tmp_path


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("schema_version", [1, 2])
def test_updates_all_clients_and_is_idempotent(
    bundle_root: Path, monkeypatch: pytest.MonkeyPatch, schema_version: int
) -> None:
    directory = bundle_root / "registry/releases/1.2.0"
    record = json.loads((directory / "index.json").read_bytes())
    record["schema_version"] = schema_version
    if schema_version == 2:
        record["datasets"][0]["schema_version"] = 2
        record["datasets"][0]["provenance"]["citations"] = [
            {"citation": "Dataset deposit.", "role": "dataset", "recommended": True}
        ]
    contents = json.dumps(record).encode()
    (directory / "index.json").write_bytes(contents)
    selector = json.loads((directory / "selector.json").read_bytes())
    selector["index_sha256"] = hashlib.sha256(contents).hexdigest()
    (directory / "selector.json").write_text(json.dumps(selector))
    calls = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return contents

    monkeypatch.setattr(dm_bundle_registry, "fetch_index", fetch)
    before = snapshot(bundle_root)
    dm_bundle_registry.bundle(bundle_root, "1.2.0")
    for directory in dm_bundle_registry.BUNDLE_DIRECTORIES:
        assert (bundle_root / directory / "index.json").read_bytes() == contents
    for path in (
        "packages/python/src/datamonger/_registry.py",
        "packages/r/R/registry.R",
        "packages/julia/src/registry.jl",
        "README.md",
    ):
        assert "1.2.0" in (bundle_root / path).read_text()
    after = snapshot(bundle_root)
    assert all(
        after[path] == data
        for path, data in before.items()
        if path.parts[0] in {"registry", "spec"}
    )
    dm_bundle_registry.bundle(bundle_root, "1.2.0")
    assert snapshot(bundle_root) == after
    assert len(calls) == 2

    def no_network(url: str) -> bytes:
        pytest.fail("offline check attempted network access")

    monkeypatch.setattr(dm_bundle_registry, "fetch_index", no_network)
    dm_bundle_registry.bundle(bundle_root, check_only=True)
    with pytest.raises(ValueError, match="downgrade"):
        dm_bundle_registry.bundle(bundle_root, "1.1.0")


def test_check_detects_drift_without_writing(bundle_root: Path) -> None:
    dm_bundle_registry.bundle(bundle_root, check_only=True)
    (bundle_root / "packages/r/inst/extdata/index.json").write_bytes(b"corrupt")
    before = snapshot(bundle_root)
    with pytest.raises(ValueError, match=r"stale.*packages/r/inst/extdata/index\.json"):
        dm_bundle_registry.bundle(bundle_root, check_only=True)
    assert snapshot(bundle_root) == before


@pytest.mark.parametrize(
    "failure",
    ["download", "index", "selector", "url", "declaration", "schema", "release"],
)
def test_failed_validation_does_not_change_files(
    bundle_root: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    directory = bundle_root / "registry/releases/1.2.0"
    contents = (directory / "index.json").read_bytes()
    monkeypatch.setattr(
        dm_bundle_registry,
        "fetch_index",
        lambda url: b"wrong" if failure == "download" else contents,
    )
    if failure == "index":
        (directory / "index.json").write_bytes(b"corrupt")
    elif failure in {"selector", "url"}:
        path = directory / "selector.json"
        selector = json.loads(path.read_bytes())
        if failure == "selector":
            selector["index_sha256"] = "0" * 64
        else:
            selector["index_url"] = "https://example.com/index.json"
        path.write_text(json.dumps(selector))
    elif failure == "declaration":
        (bundle_root / "packages/r/R/registry.R").write_text("missing declaration\n")
    elif failure in {"schema", "release"}:
        record = json.loads(contents)
        record["schema_version" if failure == "schema" else "release"] = 3
        contents = json.dumps(record).encode()
        (directory / "index.json").write_bytes(contents)
        selector = json.loads((directory / "selector.json").read_bytes())
        selector["index_sha256"] = hashlib.sha256(contents).hexdigest()
        (directory / "selector.json").write_text(json.dumps(selector))
    before = snapshot(bundle_root)
    with pytest.raises((ValueError, ValidationError)):
        dm_bundle_registry.bundle(bundle_root, "1.2.0")
    assert snapshot(bundle_root) == before


@pytest.mark.parametrize("release", ["../escape", "01.2.0", "1.2", "1.2.0-rc1", ""])
def test_rejects_invalid_releases(bundle_root: Path, release: str) -> None:
    with pytest.raises(ValueError, match="stable semantic"):
        dm_bundle_registry.bundle(bundle_root, release)
