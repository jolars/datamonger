"""Provisional registry fetching, parsing, and resolution."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from datamonger._cache import verified_download
from datamonger._errors import (
    RegistryError,
    RegistryIntegrityError,
    RegistryReleaseError,
    RegistryRetrievalError,
    UnknownDatasetError,
    UnsupportedRegistryError,
)
from datamonger._models import Registry
from datamonger._validate import require_array

_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")

BUNDLED_REGISTRY = Registry(
    release="proof-0001",
    index_sha256="98cdbc7c8c795dcd021775de4c955c2442e6e1f2d7911e4c53b72327d90f6578",
    index_url=(
        "https://github.com/jolars/datamonger/releases/download/"
        "registry-proof-0001/index.json"
    ),
)


def _require_array(value: object, field: str) -> Sequence[object]:
    return require_array(value, f"registry {field}", UnsupportedRegistryError)


def bundled_registry_bytes() -> bytes:
    """Read the registry snapshot installed with the Python package."""

    try:
        return files("datamonger._data").joinpath("index.json").read_bytes()
    except OSError as error:
        raise RegistryRetrievalError(
            f"cannot read the bundled registry index: {error}"
        ) from error


def _is_bundled_selector(registry: Registry) -> bool:
    return (
        registry.release == BUNDLED_REGISTRY.release
        and registry.index_sha256 == BUNDLED_REGISTRY.index_sha256
    )


def _registry_bytes(registry: Registry, cache_root: Path) -> bytes:
    if _is_bundled_selector(registry):
        contents = bundled_registry_bytes()
        actual = hashlib.sha256(contents).hexdigest()
        if actual != registry.index_sha256:
            raise RegistryIntegrityError(
                "bundled registry SHA-256 mismatch: "
                f"expected {registry.index_sha256}, received {actual}"
            )
        return contents

    index_path = verified_download(
        cache_root=cache_root,
        namespace="registries",
        url=registry.index_url,
        digest=registry.index_sha256,
        size=None,
        integrity_error=RegistryIntegrityError,
        retrieval_error=RegistryRetrievalError,
    )
    try:
        return index_path.read_bytes()
    except OSError as error:
        raise RegistryError(f"cannot read verified registry index: {error}") from error


def load_registry(registry: Registry, cache_root: Path) -> Mapping[str, Any]:
    """Fetch, verify, parse, and minimally validate a selected registry."""

    try:
        parsed = json.loads(_registry_bytes(registry, cache_root))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistryError(
            f"verified registry index is invalid JSON: {error}"
        ) from error
    if not isinstance(parsed, Mapping):
        raise UnsupportedRegistryError("registry index must be a JSON object")
    if parsed.get("schema_version") != 1:
        raise UnsupportedRegistryError(
            f"unsupported registry schema {parsed.get('schema_version')!r}"
        )
    if parsed.get("release") != registry.release:
        raise RegistryReleaseError(
            f"selected release {registry.release!r} does not match embedded release "
            f"{parsed.get('release')!r}"
        )
    _require_array(parsed.get("datasets"), "datasets")
    _require_array(parsed.get("defaults"), "defaults")
    return cast(Mapping[str, Any], parsed)


def _valid_identity(source: str, name: str, version: str | None) -> bool:
    return (
        _IDENTIFIER.fullmatch(source) is not None
        and _IDENTIFIER.fullmatch(name) is not None
        and (version is None or _VERSION.fullmatch(version) is not None)
    )


def resolve_dataset(
    index: Mapping[str, Any], *, source: str, name: str, version: str | None
) -> Mapping[str, Any]:
    """Resolve an explicit or default dataset version."""

    if not _valid_identity(source, name, version):
        requested = f"{source}:{name}" + (f"@{version}" if version else "")
        raise UnknownDatasetError(f"invalid or unknown dataset {requested}")

    resolved_version = version
    if resolved_version is None:
        for raw_default in _require_array(index.get("defaults"), "defaults"):
            if not isinstance(raw_default, Mapping):
                raise UnsupportedRegistryError("registry default must be an object")
            if raw_default.get("source") == source and raw_default.get("name") == name:
                candidate = raw_default.get("version")
                if not isinstance(candidate, str):
                    raise UnsupportedRegistryError("default version must be a string")
                resolved_version = candidate
                break
        if resolved_version is None:
            raise UnknownDatasetError(f"unknown dataset {source}:{name}")

    for raw_dataset in _require_array(index.get("datasets"), "datasets"):
        if not isinstance(raw_dataset, Mapping):
            raise UnsupportedRegistryError("registry dataset must be an object")
        if (
            raw_dataset.get("source") == source
            and raw_dataset.get("name") == name
            and raw_dataset.get("version") == resolved_version
        ):
            # Records carry their own schema version; a future record schema
            # inside a supported index envelope must fail loudly rather than
            # be reinterpreted under version 1 assumptions.
            if raw_dataset.get("schema_version") != 1:
                raise UnsupportedRegistryError(
                    f"unsupported dataset schema {raw_dataset.get('schema_version')!r}"
                )
            return cast(Mapping[str, Any], raw_dataset)

    raise UnknownDatasetError(f"unknown dataset {source}:{name}@{resolved_version}")
