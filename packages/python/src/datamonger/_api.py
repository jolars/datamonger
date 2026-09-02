"""Public retrieval API for the Python vertical proof."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Literal, overload

from datamonger._cache import (
    default_cache_root,
    verified_cache_lease,
    verified_download_lease,
)
from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm
from datamonger._errors import (
    ArtifactIntegrityError,
    ArtifactSelectionError,
    ArtifactUnavailableError,
    DecodedIntegrityError,
    OfflineError,
    RetrievalError,
    RetrievalLocationsError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
)
from datamonger._models import (
    DatasetData,
    FetchInfo,
    FetchResult,
    LogicalComponent,
    LogicalSparseMatrix,
    LogicalValueComponent,
    Pathish,
    Registry,
)
from datamonger._registry import load_registry, resolve_dataset
from datamonger._selection import active_registry
from datamonger._validate import (
    require_array,
    require_integer,
    require_mapping,
    require_string,
)


def _object(value: object, field: str) -> Mapping[str, Any]:
    return require_mapping(value, field, UnsupportedRegistryError)


def _array(value: object, field: str) -> Sequence[object]:
    return require_array(value, field, UnsupportedRegistryError)


def _string(value: object, field: str) -> str:
    return require_string(value, field, UnsupportedRegistryError)


def _integer(value: object, field: str) -> int:
    return require_integer(value, field, UnsupportedRegistryError)


def _load_registry(
    registry: Registry, cache_root: Path, *, offline: bool
) -> Mapping[str, Any]:
    if offline:
        return load_registry(registry, cache_root, offline=True)
    return load_registry(registry, cache_root)


def _artifacts(dataset: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        _object(raw_artifact, "artifact")
        for raw_artifact in _array(dataset.get("artifacts"), "dataset.artifacts")
    ]


def _available_artifacts(artifacts: Sequence[Mapping[str, Any]]) -> str:
    return ", ".join(
        _string(artifact.get("name"), "artifact name") for artifact in artifacts
    )


def _select_artifact(
    dataset: Mapping[str, Any], artifact_name: str | None
) -> Mapping[str, Any]:
    artifacts = _artifacts(dataset)
    available = _available_artifacts(artifacts)
    if artifact_name is None:
        if len(artifacts) == 1:
            return artifacts[0]
        raise ArtifactSelectionError(
            f"artifact name is required; available artifacts: {available or '(none)'}"
        )
    for artifact in artifacts:
        if artifact.get("name") == artifact_name:
            return artifact
    raise ArtifactSelectionError(
        f"unknown artifact {artifact_name!r}; "
        f"available artifacts: {available or '(none)'}"
    )


def _artifact_for_representation(
    dataset: Mapping[str, Any], representation: Mapping[str, Any]
) -> Mapping[str, Any]:
    inputs = _object(representation.get("inputs"), "representation.inputs")
    artifact_name = _string(inputs.get("data"), "representation.inputs.data")
    for artifact in _artifacts(dataset):
        if artifact.get("name") == artifact_name:
            return artifact
    raise UnsupportedRegistryError(
        f"representation input refers to unknown artifact {artifact_name!r}"
    )


@contextmanager
def _retrieve_artifact_lease(
    artifact: Mapping[str, Any], cache_root: Path, *, offline: bool
) -> Iterator[Path]:
    artifact_name = _string(artifact.get("name"), "artifact name")
    distribution = artifact.get("distribution")
    if distribution == "metadata-only":
        raise ArtifactUnavailableError(
            f"artifact {artifact_name!r} is metadata-only and cannot be retrieved"
        )
    if distribution not in {"mirror", "upstream-only"}:
        raise UnsupportedRegistryError(
            f"artifact {artifact_name!r} has unsupported distribution {distribution!r}"
        )
    downloads = _array(artifact.get("downloads"), "artifact.downloads")
    if not downloads:
        raise UnsupportedRegistryError("artifact declares no download locations")
    digest = _string(artifact.get("sha256"), "artifact SHA-256")
    size = _integer(artifact.get("size"), "artifact size")
    if offline:
        with verified_cache_lease(
            cache_root=cache_root,
            namespace="objects",
            digest=digest,
            size=size,
            integrity_error=ArtifactIntegrityError,
            unavailable_error=OfflineError,
            description=f"artifact {artifact_name!r}",
        ) as path:
            yield path
        return
    # Locations are tried in manifest order; a transport error or an integrity
    # mismatch moves on to the next location, and the final error must still
    # distinguish unavailability from an integrity failure.
    failures: list[str] = []
    integrity_failure = False
    for raw_download in downloads:
        download = _object(raw_download, "artifact download")
        if download.get("kind") not in {"mirror", "upstream"}:
            raise UnsupportedRegistryError("unsupported artifact download kind")
        url = _string(download.get("url"), "artifact download URL")
        stack = ExitStack()
        try:
            path = stack.enter_context(
                verified_download_lease(
                    cache_root=cache_root,
                    namespace="objects",
                    url=url,
                    digest=digest,
                    size=size,
                    integrity_error=ArtifactIntegrityError,
                )
            )
        except RetrievalError as error:
            stack.close()
            integrity_failure |= isinstance(error, ArtifactIntegrityError)
            failures.append(f"{url}: {error}")
        else:
            with stack:
                yield path
            return
    failed = ArtifactIntegrityError if integrity_failure else RetrievalLocationsError
    raise failed(f"all retrieval locations failed: {'; '.join(failures)}")


def _retrieve_artifact(
    artifact: Mapping[str, Any], cache_root: Path, *, offline: bool
) -> Path:
    with _retrieve_artifact_lease(artifact, cache_root, offline=offline) as path:
        return path


def fetch_artifact(
    name: str,
    *,
    source: str,
    version: str | None = None,
    artifact: str | None = None,
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
) -> Path:
    """Resolve and retrieve one verified artifact without decoding it.

    ``artifact`` may be omitted only when the resolved dataset version declares
    exactly one artifact. An explicit registry overrides session and project
    selection. ``offline=True`` permits verified cache hits but performs no
    network requests.
    """

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    selected_registry = registry if registry is not None else active_registry()
    index = _load_registry(selected_registry, cache_root, offline=offline)
    dataset = resolve_dataset(index, source=source, name=name, version=version)
    selected_artifact = _select_artifact(dataset, artifact)
    return _retrieve_artifact(selected_artifact, cache_root, offline=offline)


def _validate_components(
    components: Sequence[LogicalValueComponent], expected: Sequence[object]
) -> None:
    if len(components) != len(expected):
        raise DecodedIntegrityError(
            f"expected {len(expected)} components, decoded {len(components)}"
        )
    for component, raw_expectation in zip(components, expected, strict=True):
        expectation = _object(raw_expectation, "component expectation")
        if isinstance(component, LogicalComponent):
            if expectation.get("kind") != "vector":
                raise DecodedIntegrityError(
                    f"decoded component {component.name!r} has the wrong kind"
                )
            matches = (
                expectation.get("name") == component.name
                and expectation.get("type") == component.logical_type
                and expectation.get("length") == len(component.values)
            )
        elif isinstance(component, LogicalSparseMatrix):
            if expectation.get("kind") != "sparse_matrix":
                raise DecodedIntegrityError(
                    f"decoded component {component.name!r} has the wrong kind"
                )
            # Canonical form 1 has a single sparse element type, so the
            # normative manifests may omit "type" for sparse matrices.
            matches = (
                expectation.get("name") == component.name
                and expectation.get("type", component.logical_type)
                == component.logical_type
                and expectation.get("rows") == component.rows
                and expectation.get("columns") == component.columns
            )
        else:
            raise UnsupportedDecoderError("unsupported logical component")
        if not matches:
            raise DecodedIntegrityError(
                f"decoded component {component.name!r} does not match its expectation"
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
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
    verify_decoded: bool = True,
    return_info: Literal[False] = False,
) -> DatasetData: ...


@overload
def fetch_data(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
    verify_decoded: bool = True,
    return_info: Literal[True],
) -> FetchResult: ...


def fetch_data(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
    verify_decoded: bool = True,
    return_info: bool = False,
) -> DatasetData | FetchResult:
    """Resolve, retrieve, verify, and decode one registered dataset.

    An explicit registry overrides session and project selection. ``offline=True``
    requires both the selected registry and its artifact to be bundled or cached.
    """

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    selected_registry = registry if registry is not None else active_registry()
    index = _load_registry(selected_registry, cache_root, offline=offline)
    dataset = resolve_dataset(index, source=source, name=name, version=version)
    resolved_version = _string(dataset.get("version"), "dataset.version")
    representation = _object(dataset.get("representation"), "dataset.representation")
    decoder = representation.get("decoder")
    decoder_version = representation.get("decoder_version")
    if decoder_version != 1 or decoder not in {"delimited-text", "libsvm"}:
        raise UnsupportedDecoderError(
            "the vertical proof supports delimited-text and LIBSVM version 1"
        )

    artifact = _artifact_for_representation(dataset, representation)
    expected_format = "csv" if decoder == "delimited-text" else "libsvm"
    if artifact.get("compression") != "none":
        raise UnsupportedDecoderError(
            "the vertical proof supports uncompressed artifacts"
        )
    if artifact.get("format") != expected_format:
        raise UnsupportedDecoderError(
            f"decoder requires artifact format {expected_format!r}"
        )
    options = _object(representation.get("options"), "representation.options")
    with _retrieve_artifact_lease(
        artifact, cache_root, offline=offline
    ) as artifact_path:
        decoded = (
            decode_delimited_text(artifact_path, options)
            if decoder == "delimited-text"
            else decode_libsvm(artifact_path, options)
        )
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
        registry_release=selected_registry.release,
        registry_index_sha256=selected_registry.index_sha256,
        artifact_digests={artifact_name: artifact_digest},
        verification=verification,
        canonical_form=canonical_form,
        canonical_digest=canonical_digest,
    )
    if return_info:
        return FetchResult(data=decoded.data, info=info)
    return decoded.data
