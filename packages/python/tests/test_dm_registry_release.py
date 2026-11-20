from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location(
    "dm_registry_release", TOOLS / "dm_registry_release.py"
)
assert SPEC is not None and SPEC.loader is not None
dm_registry_release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_registry_release)


@pytest.fixture
def registry_root(tmp_path: Path) -> Path:
    # Release PRs already contain their pending snapshot, so use a fixed baseline.
    # Small provider manifests avoid repeatedly parsing wide curated gene tables.
    for directory in (
        "registry/datasets/libsvm",
        "registry/datasets/uci",
        "registry/releases/2026.09",
        "spec/schema",
    ):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    collection = dict(
        dm_registry_release.dm_index.load_yaml(ROOT / "registry/collection.yaml")
    )
    collection["datasets"] = {
        source: collection["datasets"][source] for source in ("libsvm", "uci")
    }
    (tmp_path / "registry/collection.yaml").write_text(
        yaml.safe_dump(collection, sort_keys=False)
    )
    (tmp_path / "registry/version.txt").write_text("1.0.0\n")
    state_directory = tmp_path / ".versionary-manifest.json.d"
    state_directory.mkdir()
    (state_directory / "registry-test.json").write_text(
        json.dumps(
            {
                "path": "registry",
                "release-target": {
                    "path": "registry",
                    "version": "1.0.0",
                    "tag": "registry-2026.09",
                },
            }
        )
        + "\n"
    )
    shutil.copyfile(
        tmp_path / "registry/releases/2026.09/selector.json",
        tmp_path / "registry/latest.json",
    )
    (tmp_path / "registry/catalog.json").write_bytes(
        dm_registry_release.dm_index.build_catalog(root=tmp_path)
    )
    return tmp_path


def bump(root: Path, version: str = "1.1.0") -> None:
    (root / "registry/version.txt").write_text(version + "\n")
    state_path = next((root / ".versionary-manifest.json.d").glob("registry-*.json"))
    state = json.loads(state_path.read_bytes())
    state["release-target"].update(version=version, tag=f"registry-v{version}")
    state_path.write_text(json.dumps(state) + "\n")


def test_legacy_release_is_the_baseline_without_a_replacement_tag(
    registry_root: Path,
) -> None:
    dm_registry_release.check(registry_root)
    with pytest.raises(ValueError, match="Versionary"):
        dm_registry_release.prepare(registry_root)
    assert not (registry_root / "registry/releases/1.0.0").exists()


def test_version_bump_requires_a_generated_snapshot(registry_root: Path) -> None:
    bump(registry_root)
    with pytest.raises((ValueError, FileNotFoundError)):
        dm_registry_release.check(registry_root)


def test_prepare_is_deterministic_and_preserves_historical_releases(
    registry_root: Path,
) -> None:
    historical = {
        path: path.read_bytes()
        for path in (registry_root / "registry/releases").rglob("*")
        if path.is_file()
    }
    bump(registry_root)
    dm_registry_release.prepare(registry_root)
    directory = registry_root / "registry/releases/1.1.0"
    first = {path: path.read_bytes() for path in directory.iterdir()}
    dm_registry_release.prepare(registry_root)
    dm_registry_release.check(registry_root, pending=True)
    assert all(path.read_bytes() == contents for path, contents in first.items())
    assert all(path.read_bytes() == contents for path, contents in historical.items())
    source = yaml.safe_load((directory / "release.yaml").read_text())
    assert source["release"] == "1.1.0"
    assert source["tag"] == "registry-v1.1.0"
    assert source["sequence"] == 4
    previous = json.loads(
        (registry_root / "registry/releases/2026.09/index.json").read_bytes()
    )
    index = json.loads((directory / "index.json").read_bytes())
    assert previous["schema_version"] == 1
    assert index["schema_version"] == max(
        record["schema_version"] for record in index["datasets"]
    )
    assert index["release"] == "1.1.0"
    for key, records in (
        ("defaults", source["defaults"]),
        (
            "datasets",
            [
                yaml.safe_load((registry_root / path).read_text())
                for path in source["manifests"]
            ],
        ),
    ):
        assert len(index[key]) == len(records)
        assert all(record in index[key] for record in records)
    assert (registry_root / "registry/latest.json").read_bytes() == (
        directory / "selector.json"
    ).read_bytes()
    catalog = json.loads((registry_root / "registry/catalog.json").read_bytes())
    assert json.loads((directory / "selector.json").read_bytes()) in catalog["releases"]


def test_pending_check_reuses_manifests_and_decoded_indexes(
    registry_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bump(registry_root)
    dm_registry_release.prepare(registry_root)
    index_builder = dm_registry_release.dm_index
    load_yaml = index_builder._load_yaml
    load_json = index_builder._load_json
    manifest_loads: Counter[str] = Counter()
    index_loads: Counter[str] = Counter()

    def count_yaml(path: Path) -> Mapping[str, Any]:
        if "datasets" in path.parts:
            manifest_loads[path.name] += 1
        return load_yaml(path)

    def count_json(path: Path, contents: bytes | None = None) -> Mapping[str, Any]:
        if path.name == "index.json":
            index_loads[path.parent.name] += 1
        return load_json(path, contents)

    monkeypatch.setattr(index_builder, "_load_yaml", count_yaml)
    monkeypatch.setattr(index_builder, "_load_json", count_json)
    dm_registry_release.check(registry_root, pending=True)

    assert manifest_loads
    assert set(manifest_loads.values()) == {1}
    assert index_loads == {"2026.09": 1, "1.1.0": 1}


def test_prepare_uses_the_last_listed_version_as_default(registry_root: Path) -> None:
    bump(registry_root)
    path = registry_root / "registry/collection.yaml"
    collection = yaml.safe_load(path.read_text())
    collection["datasets"]["uci"]["iris"]["versions"] = ["1", "0"]
    path.write_text(yaml.safe_dump(collection))
    iris = registry_root / "registry/datasets/uci/iris-1.yaml"
    manifest = yaml.safe_load(iris.read_text())
    manifest["version"] = "0"
    iris.with_name("iris-0.yaml").write_text(yaml.safe_dump(manifest))

    dm_registry_release.prepare(registry_root)
    index = json.loads(
        (registry_root / "registry/releases/1.1.0/index.json").read_bytes()
    )
    assert {
        record["version"] for record in index["datasets"] if record["name"] == "iris"
    } == {
        "0",
        "1",
    }
    defaults = {
        (record["source"], record["name"]): record["version"]
        for record in index["defaults"]
    }
    assert defaults["uci", "iris"] == "0"
    assert defaults["uci", "abalone"] == "1"


@pytest.mark.parametrize(
    ("versions", "error", "message"),
    [
        ([], ValueError, "non-empty"),
        (["1", "1"], ValueError, "non-unique"),
        ([1], ValueError, "not of type 'string'"),
        (["missing"], FileNotFoundError, "iris-missing"),
    ],
)
def test_invalid_source_leaves_no_partial_release(
    registry_root: Path,
    versions: list[str | int],
    error: type[Exception],
    message: str,
) -> None:
    bump(registry_root)
    path = registry_root / "registry/collection.yaml"
    source = yaml.safe_load(path.read_text())
    source["datasets"]["uci"]["iris"]["versions"] = versions
    path.write_text(yaml.safe_dump(source))
    latest = (registry_root / "registry/latest.json").read_bytes()
    catalog = (registry_root / "registry/catalog.json").read_bytes()
    with pytest.raises(error, match=message):
        dm_registry_release.prepare(registry_root)
    assert not (registry_root / "registry/releases/1.1.0").exists()
    assert (registry_root / "registry/latest.json").read_bytes() == latest
    assert (registry_root / "registry/catalog.json").read_bytes() == catalog


def test_prepare_rejects_mismatched_manifest_identity(registry_root: Path) -> None:
    bump(registry_root)
    path = registry_root / "registry/collection.yaml"
    collection = yaml.safe_load(path.read_text())
    collection["datasets"]["uci"]["iris"]["versions"] = ["2", "1"]
    path.write_text(yaml.safe_dump(collection))
    iris = registry_root / "registry/datasets/uci/iris-1.yaml"
    # The default still identifies an available version, but the first entry does not.
    shutil.copyfile(iris, iris.with_name("iris-2.yaml"))
    with pytest.raises(ValueError, match=r"manifest identity .* does not match"):
        dm_registry_release.prepare(registry_root)


@pytest.mark.parametrize("filename", ["release.yaml", "index.json", "selector.json"])
def test_prepare_refuses_to_replace_an_existing_snapshot(
    registry_root: Path, filename: str
) -> None:
    bump(registry_root)
    dm_registry_release.prepare(registry_root)
    path = registry_root / "registry/releases/1.1.0" / filename
    path.write_bytes(b"different\n")
    with pytest.raises(ValueError):
        dm_registry_release.prepare(registry_root)
    assert path.read_bytes() == b"different\n"


@pytest.mark.parametrize("version", ["../escape", "01.1.0", "1.0", "v1.1.0"])
def test_invalid_versions_cannot_select_paths(
    registry_root: Path, version: str
) -> None:
    bump(registry_root, version)
    with pytest.raises(ValueError, match="version"):
        dm_registry_release.prepare(registry_root)


def test_versionary_target_must_agree_with_version_file(registry_root: Path) -> None:
    bump(registry_root)
    (registry_root / "registry/version.txt").write_text("1.2.0\n")
    with pytest.raises(ValueError, match="Versionary"):
        dm_registry_release.prepare(registry_root)


def test_pending_check_rejects_a_stale_collection(registry_root: Path) -> None:
    bump(registry_root)
    dm_registry_release.prepare(registry_root)
    path = registry_root / "registry/collection.yaml"
    source = yaml.safe_load(path.read_text())
    del source["datasets"]["uci"]["iris"]
    path.write_text(yaml.safe_dump(source))
    with pytest.raises(ValueError):
        dm_registry_release.check(registry_root, pending=True)


def test_check_rejects_a_stale_latest_selector(registry_root: Path) -> None:
    (registry_root / "registry/latest.json").write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="latest"):
        dm_registry_release.check(registry_root)
