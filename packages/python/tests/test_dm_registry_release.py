from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

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
    for directory in ("registry", "spec/schema", ".versionary-manifest.json.d"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
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
    assert json.loads((directory / "index.json").read_bytes()) == {
        **previous,
        "release": "1.1.0",
    }
    assert (registry_root / "registry/latest.json").read_bytes() == (
        directory / "selector.json"
    ).read_bytes()
    catalog = json.loads((registry_root / "registry/catalog.json").read_bytes())
    assert json.loads((directory / "selector.json").read_bytes()) in catalog["releases"]


def test_invalid_source_leaves_no_partial_release(registry_root: Path) -> None:
    bump(registry_root)
    path = registry_root / "registry/collection.yaml"
    source = yaml.safe_load(path.read_text())
    source["defaults"][0]["version"] = "missing"
    path.write_text(yaml.safe_dump(source))
    latest = (registry_root / "registry/latest.json").read_bytes()
    catalog = (registry_root / "registry/catalog.json").read_bytes()
    with pytest.raises(ValueError, match="unknown datasets"):
        dm_registry_release.prepare(registry_root)
    assert not (registry_root / "registry/releases/1.1.0").exists()
    assert (registry_root / "registry/latest.json").read_bytes() == latest
    assert (registry_root / "registry/catalog.json").read_bytes() == catalog


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
    source["defaults"].pop()
    path.write_text(yaml.safe_dump(source))
    with pytest.raises(ValueError):
        dm_registry_release.check(registry_root, pending=True)


def test_check_rejects_a_stale_latest_selector(registry_root: Path) -> None:
    (registry_root / "registry/latest.json").write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="latest"):
        dm_registry_release.check(registry_root)
