from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Self

import pytest

from datamonger import BUNDLED_REGISTRY, Registry, _registry, resolve_registry
from datamonger.errors import (
    RegistryError,
    RegistryIntegrityError,
    RegistryRetrievalError,
    UnsupportedRegistryError,
)


class CatalogResponse:
    def __init__(
        self,
        contents: bytes,
        url: str = "https://catalog.example/releases.json",
    ) -> None:
        self.contents = contents
        self.url = url

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def read(self) -> bytes:
        return self.contents

    def geturl(self) -> str:
        return self.url


def catalog_bytes(*selectors: Registry) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "releases": [
                {
                    "release": selector.release,
                    "index_sha256": selector.index_sha256,
                    "index_url": selector.index_url,
                }
                for selector in selectors
            ],
        }
    ).encode()


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


def test_resolve_registry_returns_strong_selector_from_https_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = Registry(
        release="2026.09",
        index_sha256="1" * 64,
        index_url="https://example.com/2026.09/index.json",
    )
    requests: list[tuple[str, str | None, float | None]] = []

    def open_catalog(
        request: urllib.request.Request, *, timeout: float | None = None
    ) -> CatalogResponse:
        requests.append(
            (
                request.full_url,
                request.get_header("Accept-encoding"),
                timeout,
            )
        )
        return CatalogResponse(catalog_bytes(BUNDLED_REGISTRY, expected))

    monkeypatch.setattr(_registry.urllib.request, "urlopen", open_catalog)

    resolved = resolve_registry(
        "2026.09", catalog_url="https://catalog.example/releases.json"
    )

    assert resolved == expected
    assert resolved.index_sha256 == "1" * 64
    assert requests == [("https://catalog.example/releases.json", "identity", 30)]


def test_resolve_registry_requires_an_explicit_release_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _registry.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("invalid names must fail before I/O"),
    )

    with pytest.raises(RegistryError, match="nonempty string"):
        resolve_registry("")


def test_resolve_registry_requires_https_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _registry.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("HTTP catalogs must fail before I/O"),
    )

    with pytest.raises(RegistryError, match="HTTPS"):
        resolve_registry("proof-0001", catalog_url="http://example.com/catalog.json")


def test_resolve_registry_classifies_catalog_transport_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> CatalogResponse:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(_registry.urllib.request, "urlopen", fail)

    with pytest.raises(RegistryRetrievalError, match="cannot retrieve catalog"):
        resolve_registry("proof-0001")


def test_resolve_registry_rejects_https_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _registry.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: CatalogResponse(
            catalog_bytes(BUNDLED_REGISTRY),
            url="http://catalog.example/releases.json",
        ),
    )

    with pytest.raises(RegistryRetrievalError, match="non-HTTPS"):
        resolve_registry("proof-0001")


def test_resolve_registry_rejects_unknown_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        _registry.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: CatalogResponse(catalog_bytes(BUNDLED_REGISTRY)),
    )

    with pytest.raises(RegistryError, match="unknown registry release 'absent'"):
        resolve_registry("absent")


@pytest.mark.parametrize(
    ("contents", "error", "message"),
    [
        (b"not JSON", RegistryError, "invalid JSON"),
        (
            '{"schema_version":1,"releases":[]}'.encode("utf-16"),
            RegistryError,
            "invalid JSON",
        ),
        (b"[]", RegistryError, "JSON object"),
        (
            b'{"schema_version":2,"releases":[]}',
            UnsupportedRegistryError,
            "catalog schema",
        ),
        (b'{"schema_version":1}', RegistryError, "exactly"),
        (
            b'{"schema_version":1,"releases":{},"extra":true}',
            RegistryError,
            "exactly",
        ),
        (
            b'{"schema_version":1,"releases":[{"release":"r",'
            b'"index_sha256":"00000000000000000000000000000000'
            b'00000000000000000000000000000000",'
            b'"index_url":"https://example.com/index.json","extra":true}]}',
            RegistryError,
            "selector must contain exactly",
        ),
        (
            b'{"schema_version":1,"releases":[{"release":"r",'
            b'"index_sha256":"invalid",'
            b'"index_url":"https://example.com/index.json"}]}',
            RegistryIntegrityError,
            "SHA-256",
        ),
        (
            catalog_bytes(
                Registry("r", "0" * 64, "https://example.com/one.json"),
                Registry("r", "1" * 64, "https://example.com/two.json"),
            ),
            RegistryError,
            "duplicate release",
        ),
    ],
)
def test_resolve_registry_rejects_malformed_catalogs(
    monkeypatch: pytest.MonkeyPatch,
    contents: bytes,
    error: type[RegistryError],
    message: str,
) -> None:
    monkeypatch.setattr(
        _registry.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: CatalogResponse(contents),
    )

    with pytest.raises(error, match=message):
        resolve_registry("r")
