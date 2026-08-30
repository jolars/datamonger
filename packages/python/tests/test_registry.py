from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from datamonger import BUNDLED_REGISTRY, _registry
from datamonger.errors import RegistryIntegrityError


def test_bundled_registry_loads_without_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_download(**_: object) -> Path:
        raise AssertionError("the bundled registry must not use the network")

    monkeypatch.setattr(_registry, "verified_download", fail_download)

    index = _registry.load_registry(BUNDLED_REGISTRY, tmp_path)

    assert index["release"] == BUNDLED_REGISTRY.release
    assert {dataset["name"] for dataset in index["datasets"]} == {
        "heart_scale",
        "iris",
    }


def test_bundled_registry_bytes_match_the_trusted_digest() -> None:
    contents = _registry.bundled_registry_bytes()

    assert hashlib.sha256(contents).hexdigest() == BUNDLED_REGISTRY.index_sha256
    assert json.loads(contents)["release"] == BUNDLED_REGISTRY.release


def test_corrupt_bundled_registry_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(_registry, "bundled_registry_bytes", lambda: b"{}")

    with pytest.raises(RegistryIntegrityError, match="bundled registry SHA-256"):
        _registry.load_registry(BUNDLED_REGISTRY, tmp_path)
