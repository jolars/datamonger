from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

_TOOL = Path(__file__).resolve().parents[3] / "tools" / "build_proof_index.py"
_SPEC = importlib.util.spec_from_file_location("build_proof_index", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
build_proof_index = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_proof_index)


def make_manifest(
    *,
    source: str = "uci",
    name: str = "iris",
    version: str = "1",
    schema_version: int = 1,
    sha256: str = "a" * 64,
    digest: str = "b" * 64,
) -> dict[str, Any]:
    return {
        "schema_version": schema_version,
        "source": source,
        "name": name,
        "version": version,
        "artifacts": [{"name": "data", "sha256": sha256}],
        "representation": {"expect": {"verification": [{"digest": digest}]}},
    }


def make_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifests: list[dict[str, Any]],
    defaults: list[dict[str, str]],
) -> Path:
    manifest_directory = tmp_path / "manifests"
    manifest_directory.mkdir()
    paths = []
    for number, manifest in enumerate(manifests):
        path = manifest_directory / f"manifest-{number}.yaml"
        path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        paths.append(str(path.relative_to(tmp_path)))
    release = {
        "release": "proof-test",
        "repository": "jolars/datamonger",
        "tag": "test",
        "manifests": paths,
        "defaults": defaults,
    }
    release_path = tmp_path / "release.yaml"
    release_path.write_text(yaml.safe_dump(release), encoding="utf-8")
    monkeypatch.setattr(build_proof_index, "ROOT", tmp_path)
    return release_path


def test_valid_release_builds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release_path = make_release(
        tmp_path,
        monkeypatch,
        [make_manifest()],
        [{"source": "uci", "name": "iris", "version": "1"}],
    )

    index_bytes, selector_bytes = build_proof_index.build(release_path)

    assert index_bytes.endswith(b"\n")
    assert selector_bytes.endswith(b"\n")


def test_two_default_versions_for_one_dataset_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = make_release(
        tmp_path,
        monkeypatch,
        [make_manifest(version="1"), make_manifest(version="2")],
        [
            {"source": "uci", "name": "iris", "version": "1"},
            {"source": "uci", "name": "iris", "version": "2"},
        ],
    )

    with pytest.raises(ValueError, match="at most one default"):
        build_proof_index.build(release_path)


def test_identifier_grammar_is_enforced_at_build_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = make_release(
        tmp_path,
        monkeypatch,
        [make_manifest(source="UCI")],
        [{"source": "UCI", "name": "iris", "version": "1"}],
    )

    with pytest.raises(ValueError, match="grammar"):
        build_proof_index.build(release_path)


def test_digest_grammar_is_enforced_at_build_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = make_release(
        tmp_path,
        monkeypatch,
        [make_manifest(sha256="A" * 64)],
        [{"source": "uci", "name": "iris", "version": "1"}],
    )

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        build_proof_index.build(release_path)


def test_unsupported_manifest_schema_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release_path = make_release(
        tmp_path,
        monkeypatch,
        [make_manifest(schema_version=2)],
        [{"source": "uci", "name": "iris", "version": "1"}],
    )

    with pytest.raises(ValueError, match="manifest schema"):
        build_proof_index.build(release_path)
