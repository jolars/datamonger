from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from datamonger import (
    BUNDLED_REGISTRY,
    Registry,
    active_registry,
    fetch_data,
    set_registry,
)
from datamonger.errors import RegistryError, UnknownDatasetError


@pytest.fixture(autouse=True)
def reset_session_registry() -> Iterator[None]:
    set_registry(None)
    yield
    set_registry(None)


def registry(label: str) -> Registry:
    return Registry(
        release=label,
        index_sha256=(label.encode().hex() + "0" * 64)[:64],
        index_url=f"https://example.com/{label}/index.json",
    )


def write_project_selector(root: Path, selected: Registry) -> Path:
    path = root / ".datamonger" / "selector.json"
    path.parent.mkdir()
    path.write_text(
        json.dumps(
            {
                "release": selected.release,
                "index_sha256": selected.index_sha256,
                "index_url": selected.index_url,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_bundled_registry_is_active_without_other_configuration(tmp_path: Path) -> None:
    assert active_registry(project_dir=tmp_path) == BUNDLED_REGISTRY


def test_nearest_project_selector_is_discovered_from_a_descendant(
    tmp_path: Path,
) -> None:
    outer = registry("outer")
    inner = registry("inner")
    write_project_selector(tmp_path, outer)
    descendant = tmp_path / "analysis" / "notebooks"
    descendant.mkdir(parents=True)
    write_project_selector(tmp_path / "analysis", inner)

    assert active_registry(project_dir=descendant) == inner


def test_session_selector_overrides_project_and_can_be_cleared(
    tmp_path: Path,
) -> None:
    project = registry("project")
    session = registry("session")
    write_project_selector(tmp_path, project)

    set_registry(session)
    assert active_registry(project_dir=tmp_path) == session

    set_registry(None)
    assert active_registry(project_dir=tmp_path) == project


def test_fetch_call_selector_overrides_session_and_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = registry("project")
    session = registry("session")
    call = registry("call")
    write_project_selector(tmp_path, project)
    monkeypatch.chdir(tmp_path)
    set_registry(session)
    selected: list[Registry] = []

    def record_registry(value: Registry, cache_root: Path) -> dict[str, object]:
        selected.append(value)
        raise UnknownDatasetError("stop after registry selection")

    monkeypatch.setattr("datamonger._api.load_registry", record_registry)

    with pytest.raises(UnknownDatasetError, match="stop after registry selection"):
        fetch_data("iris", source="uci", registry=call)

    assert selected == [call]


def test_fetch_uses_session_then_project_selectors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    project = registry("project")
    session = registry("session")
    write_project_selector(tmp_path, project)
    monkeypatch.chdir(tmp_path)
    selected: list[Registry] = []

    def record_registry(value: Registry, cache_root: Path) -> dict[str, object]:
        selected.append(value)
        raise UnknownDatasetError("stop after registry selection")

    monkeypatch.setattr("datamonger._api.load_registry", record_registry)

    set_registry(session)
    with pytest.raises(UnknownDatasetError, match="stop after registry selection"):
        fetch_data("iris", source="uci")
    set_registry(None)
    with pytest.raises(UnknownDatasetError, match="stop after registry selection"):
        fetch_data("iris", source="uci")

    assert selected == [session, project]


@pytest.mark.parametrize(
    "contents, message",
    [
        (b"not JSON", "invalid JSON"),
        (b"[]", "JSON object"),
        (b'{"release":"only"}', "exactly"),
        (
            b'{"release":"r","index_sha256":"00000000000000000000000000000000'
            b'00000000000000000000000000000000","index_url":"https://example.com",'
            b'"latest":true}',
            "exactly",
        ),
        (
            b'{"release":"r","index_sha256":"not-a-digest",'
            b'"index_url":"https://example.com"}',
            "SHA-256",
        ),
        (
            b'{"release":"r","index_sha256":"00000000000000000000000000000000'
            b'00000000000000000000000000000000","index_url":"relative/index.json"}',
            "absolute URI",
        ),
    ],
)
def test_invalid_project_selector_fails_without_falling_back(
    tmp_path: Path, contents: bytes, message: str
) -> None:
    path = tmp_path / ".datamonger" / "selector.json"
    path.parent.mkdir()
    path.write_bytes(contents)

    with pytest.raises(RegistryError, match=message):
        active_registry(project_dir=tmp_path)


def test_invalid_session_selector_is_rejected(tmp_path: Path) -> None:
    invalid = Registry(
        release="release",
        index_sha256="not-a-digest",
        index_url="https://example.com/index.json",
    )

    with pytest.raises(RegistryError, match="SHA-256"):
        set_registry(invalid)

    assert active_registry(project_dir=tmp_path) == BUNDLED_REGISTRY


def test_project_selector_path_must_be_a_file(tmp_path: Path) -> None:
    path = tmp_path / ".datamonger" / "selector.json"
    path.mkdir(parents=True)

    with pytest.raises(RegistryError, match="must be a file"):
        active_registry(project_dir=tmp_path)
