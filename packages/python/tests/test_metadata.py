from __future__ import annotations

import json
from pathlib import Path

import pytest

from datamonger import BUNDLED_REGISTRY, DataInfo, Registry, _api, data_info, list_data
from datamonger.errors import UnknownDatasetError


def bundled_index() -> dict[str, object]:
    return json.loads(
        (
            Path(__file__).resolve().parents[1] / "src/datamonger/_data/index.json"
        ).read_bytes()
    )


@pytest.fixture
def loaded_bundled_registry(monkeypatch: pytest.MonkeyPatch) -> Registry:
    index = bundled_index()
    selected = Registry("test-release", "1" * 64, "https://example.invalid/index")
    monkeypatch.setattr(_api, "_load_registry", lambda *_args, **_kwargs: index)
    return selected


def test_data_info_resolves_defaults_and_exposes_registry_metadata(
    loaded_bundled_registry: Registry, tmp_path: Path
) -> None:
    info = data_info(
        "iris",
        source="uci",
        registry=loaded_bundled_registry,
        cache_dir=tmp_path,
    )

    assert isinstance(info, DataInfo)
    assert info.dataset_id == "uci:iris@1"
    assert (info.source, info.name, info.version, info.is_default) == (
        "uci",
        "iris",
        "1",
        True,
    )
    assert info.registry_release == "test-release"
    assert info.registry_index_sha256 == "1" * 64
    assert info.title == "Iris"
    assert info.description.startswith("Fisher's Iris")
    assert info.modality == "tabular"
    assert info.provenance["provider"] == "UCI Machine Learning Repository"
    assert info.license["identifier"] == "CC-BY-4.0"
    assert info.artifacts[0]["name"] == "data"
    assert info.artifacts[0]["sha256"] == (
        "daaeb5e3e889d07fbdd44544f5a39fe2372a07172e25899d577be0ad74df9e65"
    )
    assert info.artifacts[0]["distribution"] == "upstream-only"
    assert info.representation["decoder"] == "delimited-text"
    expect = info.representation["expect"]
    assert isinstance(expect, dict)
    assert expect["components"][0] == {
        "kind": "vector",
        "length": 150,
        "name": "sepal length",
        "type": "float64",
    }
    assert expect["verification"][0]["canonical_form"] == 1
    assert info.expected_components[0] == expect["components"][0]
    assert info.verification_records[0] == expect["verification"][0]
    assert info.related == ()
    assert info.tasks[0]["name"] == "default"


def test_list_data_enumerates_the_selected_release_in_canonical_order(
    loaded_bundled_registry: Registry, tmp_path: Path
) -> None:
    infos = list_data(registry=loaded_bundled_registry, cache_dir=tmp_path)

    assert isinstance(infos, tuple)
    assert all(isinstance(info, DataInfo) for info in infos)
    assert [info.dataset_id for info in infos] == [
        "libsvm:heart_scale@1",
        "uci:iris@1",
    ]
    assert all(info.is_default for info in infos)
    assert {info.representation["decoder"] for info in infos} == {
        "delimited-text",
        "libsvm",
    }
    assert all(info.registry_release == "test-release" for info in infos)


def test_data_info_uses_fetch_resolution_errors(
    loaded_bundled_registry: Registry, tmp_path: Path
) -> None:
    with pytest.raises(UnknownDatasetError, match="unknown dataset"):
        data_info(
            "missing",
            source="uci",
            registry=loaded_bundled_registry,
            cache_dir=tmp_path,
        )


def test_metadata_operations_forward_offline_registry_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[Registry, Path, bool]] = []

    def load(
        registry: Registry, cache_root: Path, *, offline: bool
    ) -> dict[str, object]:
        calls.append((registry, cache_root, offline))
        return bundled_index()

    monkeypatch.setattr(_api, "_load_registry", load)

    data_info(
        "iris",
        source="uci",
        registry=BUNDLED_REGISTRY,
        cache_dir=tmp_path,
        offline=True,
    )
    list_data(registry=BUNDLED_REGISTRY, cache_dir=tmp_path, offline=True)

    assert calls == [
        (BUNDLED_REGISTRY, tmp_path, True),
        (BUNDLED_REGISTRY, tmp_path, True),
    ]
