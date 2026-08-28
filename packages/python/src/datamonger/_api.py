"""Public retrieval API for the Python vertical proof."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, overload

import pandas as pd

from datamonger._cache import default_cache_root, verified_download
from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._errors import (
    ArtifactIntegrityError,
    DecodedIntegrityError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
)
from datamonger._models import FetchInfo, FetchResult, Pathish, Registry
from datamonger._registry import load_registry, resolve_dataset


def _object(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UnsupportedRegistryError(f"{field} must be an object")
    return value


def _array(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise UnsupportedRegistryError(f"{field} must be an array")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise UnsupportedRegistryError(f"{field} must be a string")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsupportedRegistryError(f"{field} must be an integer")
    return value


def _artifact_for_representation(
    dataset: Mapping[str, Any], representation: Mapping[str, Any]
) -> Mapping[str, Any]:
    inputs = _object(representation.get("inputs"), "representation.inputs")
    artifact_name = _string(inputs.get("data"), "representation.inputs.data")
    artifacts = _array(dataset.get("artifacts"), "dataset.artifacts")
    for raw_artifact in artifacts:
        artifact = _object(raw_artifact, "artifact")
        if artifact.get("name") == artifact_name:
            return artifact
    raise UnsupportedRegistryError(
        f"representation input refers to unknown artifact {artifact_name!r}"
    )


def _fetch_artifact(artifact: Mapping[str, Any], cache_root: Path) -> Path:
    if artifact.get("distribution") != "upstream-only":
        raise UnsupportedRegistryError("slice 0A supports upstream-only artifacts")
    if artifact.get("compression") != "none" or artifact.get("format") != "csv":
        raise UnsupportedDecoderError("slice 0A supports uncompressed CSV artifacts")
    downloads = _array(artifact.get("downloads"), "artifact.downloads")
    if len(downloads) != 1:
        raise UnsupportedRegistryError("slice 0A requires exactly one download")
    download = _object(downloads[0], "artifact download")
    if download.get("kind") != "upstream":
        raise UnsupportedRegistryError("slice 0A requires an upstream download")
    return verified_download(
        cache_root=cache_root,
        namespace="objects",
        url=_string(download.get("url"), "artifact download URL"),
        digest=_string(artifact.get("sha256"), "artifact SHA-256"),
        size=_integer(artifact.get("size"), "artifact size"),
        integrity_error=ArtifactIntegrityError,
    )


def _validate_components(
    components: Sequence[object], expected: Sequence[object]
) -> None:
    if len(components) != len(expected):
        raise DecodedIntegrityError(
            f"expected {len(expected)} components, decoded {len(components)}"
        )
    for component, raw_expectation in zip(components, expected, strict=True):
        expectation = _object(raw_expectation, "component expectation")
        name = getattr(component, "name", None)
        logical_type = getattr(component, "logical_type", None)
        values = getattr(component, "values", ())
        if expectation.get("kind") != "vector":
            raise UnsupportedDecoderError("slice 0A supports vector components")
        if (
            expectation.get("name") != name
            or expectation.get("type") != logical_type
            or expectation.get("length") != len(values)
        ):
            raise DecodedIntegrityError(
                f"decoded component {name!r} does not match its expectation"
            )


def _verification_record(expect: Mapping[str, Any]) -> Mapping[str, Any]:
    records = _array(expect.get("verification"), "representation.expect.verification")
    for raw_record in records:
        record = _object(raw_record, "verification record")
        if record.get("canonical_form") == 1 and record.get("algorithm") == "sha256":
            return record
    raise UnsupportedDecoderError("no supported decoded-verification record")


@overload
def fetch_data(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry,
    cache_dir: Pathish | None = None,
    verify_decoded: bool = True,
    return_info: Literal[False] = False,
) -> pd.DataFrame: ...


@overload
def fetch_data(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry,
    cache_dir: Pathish | None = None,
    verify_decoded: bool = True,
    return_info: Literal[True],
) -> FetchResult: ...


def fetch_data(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry,
    cache_dir: Pathish | None = None,
    verify_decoded: bool = True,
    return_info: bool = False,
) -> pd.DataFrame | FetchResult:
    """Resolve, retrieve, verify, and decode one registered dataset."""

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    index = load_registry(registry, cache_root)
    dataset = resolve_dataset(index, source=source, name=name, version=version)
    resolved_version = _string(dataset.get("version"), "dataset.version")
    representation = _object(dataset.get("representation"), "dataset.representation")
    if (
        representation.get("decoder") != "delimited-text"
        or representation.get("decoder_version") != 1
    ):
        raise UnsupportedDecoderError("slice 0A supports delimited-text version 1")

    artifact = _artifact_for_representation(dataset, representation)
    artifact_path = _fetch_artifact(artifact, cache_root)
    options = _object(representation.get("options"), "representation.options")
    decoded = decode_delimited_text(artifact_path, options)
    expect = _object(representation.get("expect"), "representation.expect")
    _validate_components(
        decoded.components,
        _array(expect.get("components"), "representation.expect.components"),
    )

    canonical_form: int | None = None
    canonical_digest: str | None = None
    verification: Literal["artifact", "decoded"] = "artifact"
    if verify_decoded:
        record = _verification_record(expect)
        canonical_form = _integer(record.get("canonical_form"), "canonical form")
        expected_digest = _string(record.get("digest"), "canonical digest")
        canonical_digest = canonical_sha256(decoded.components)
        if canonical_digest != expected_digest:
            raise DecodedIntegrityError(
                f"decoded SHA-256 mismatch: expected {expected_digest}, "
                f"received {canonical_digest}"
            )
        verification = "decoded"

    dataset_id = f"{source}:{name}@{resolved_version}"
    artifact_name = _string(artifact.get("name"), "artifact name")
    artifact_digest = _string(artifact.get("sha256"), "artifact SHA-256")
    info = FetchInfo(
        dataset_id=dataset_id,
        registry_release=registry.release,
        registry_index_sha256=registry.index_sha256,
        artifact_digests={artifact_name: artifact_digest},
        verification=verification,
        canonical_form=canonical_form,
        canonical_digest=canonical_digest,
    )
    if return_info:
        return FetchResult(data=decoded.data, info=info)
    return decoded.data
