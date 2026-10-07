from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from conftest import CONFORMANCE_ARTIFACTS_BY_SHA256, CORPUS

from datamonger import Registry, data_info, fetch_artifact, fetch_data
from datamonger.errors import UnknownDatasetError


@pytest.fixture
def seeded_registry(tmp_path: Path) -> Registry:
    release = CORPUS.parent / "registry/releases/test-0002"
    registry = Registry(**json.loads((release / "selector.json").read_bytes()))
    registry_dir = tmp_path / "registries/sha256"
    registry_dir.mkdir(parents=True)
    (registry_dir / registry.index_sha256).write_bytes(
        (release / "index.json").read_bytes()
    )
    object_dir = tmp_path / "objects/sha256"
    object_dir.mkdir(parents=True)
    for digest, path in CONFORMANCE_ARTIFACTS_BY_SHA256.items():
        (object_dir / digest).write_bytes(path.read_bytes())
    return registry


@pytest.mark.parametrize(
    ("name", "source", "version"),
    [
        ("mixed_csv", "conformance", None),
        ("conformance:mixed_csv", None, None),
        ("conformance:mixed_csv", None, "1"),
        ("conformance:mixed_csv@1", None, None),
    ],
)
def test_dataset_references_select_the_same_data_artifact_and_metadata(
    name: str,
    source: str | None,
    version: str | None,
    seeded_registry: Registry,
    tmp_path: Path,
) -> None:
    options: dict[str, Any] = dict(
        registry=seeded_registry,
        cache_dir=tmp_path,
        offline=True,
    )
    if source is not None:
        options["source"] = source
    if version is not None:
        options["version"] = version
    info = data_info(name, **options)
    result = fetch_data(name, **options, return_info=True)
    artifact = fetch_artifact(name, **options)

    assert info.dataset_id == result.info.dataset_id == "conformance:mixed_csv@1"
    assert (info.source, info.name, info.version) == ("conformance", "mixed_csv", "1")
    assert result.info.verification == "decoded"
    assert isinstance(result.data, pd.DataFrame)
    assert result.data.shape == (5, 4)
    assert artifact.read_bytes() == (CORPUS / "artifacts/mixed.csv").read_bytes()


@pytest.mark.parametrize("operation", [fetch_data, data_info, fetch_artifact])
@pytest.mark.parametrize(
    ("name", "source", "version", "message"),
    [
        ("mixed_csv", None, None, "source is required"),
        ("conformance:mixed_csv", "conformance", None, "source"),
        ("conformance:mixed_csv", "other", None, "source"),
        ("conformance:mixed_csv@1", None, "1", "version"),
        ("conformance:mixed_csv@1", None, "2", "version"),
    ],
)
def test_ambiguous_arguments_fail_before_registry_loading(
    operation: Callable[..., Any],
    name: str,
    source: str | None,
    version: str | None,
    message: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match=message):
        operation(
            name,
            source=source,
            version=version,
            registry=Registry("uncached", "0" * 64, "https://example.invalid/index"),
            cache_dir=tmp_path,
            offline=True,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("operation", [fetch_data, data_info, fetch_artifact])
@pytest.mark.parametrize(
    "name",
    [
        ":mixed_csv",
        "conformance:",
        "conformance:mixed_csv@",
        "conformance:mixed_csv@1@2",
        "conformance:other:mixed_csv",
        " conformance:mixed_csv",
        "conformance:mixed_csv\n",
        "Conformance:mixed_csv",
        "conformance:mixed/csv",
        "mixed_csv@1",
    ],
)
def test_malformed_references_are_unknown_datasets(
    operation: Callable[..., Any], name: str, tmp_path: Path
) -> None:
    with pytest.raises(UnknownDatasetError):
        operation(
            name,
            registry=Registry("uncached", "0" * 64, "https://example.invalid/index"),
            cache_dir=tmp_path,
            offline=True,
        )


@pytest.mark.parametrize("name", ["conformance:missing", "conformance:mixed_csv@2"])
def test_qualified_references_preserve_resolution_errors(
    name: str, seeded_registry: Registry, tmp_path: Path
) -> None:
    with pytest.raises(UnknownDatasetError):
        data_info(name, registry=seeded_registry, cache_dir=tmp_path, offline=True)
