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
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
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
    DataInfo,
    DatasetData,
    DecodedSparseDataset,
    DecodedSparseDatasetSplit,
    DecodedTable,
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


def _artifacts_for_representation(
    dataset: Mapping[str, Any],
    representation: Mapping[str, Any],
    roles: Sequence[str],
) -> tuple[Mapping[str, Any], ...]:
    inputs = _object(representation.get("inputs"), "representation.inputs")
    if set(inputs) != set(roles):
        raise UnsupportedRegistryError(
            f"representation inputs must be exactly {list(roles)!r}"
        )
    artifacts = _artifacts(dataset)
    selected: list[Mapping[str, Any]] = []
    for role in roles:
        artifact_name = _string(inputs.get(role), f"representation.inputs.{role}")
        for artifact in artifacts:
            if artifact.get("name") == artifact_name:
                selected.append(artifact)
                break
        else:
            raise UnsupportedRegistryError(
                f"representation input refers to unknown artifact {artifact_name!r}"
            )
    return tuple(selected)


def _libsvm_compression(artifact: Mapping[str, Any]) -> str:
    artifact_format = artifact.get("format")
    if artifact_format not in {"libsvm", "svmlight"}:
        raise UnsupportedDecoderError(
            "LIBSVM decoding requires a LIBSVM or SVMLight artifact"
        )
    compression = artifact.get("compression")
    if not isinstance(compression, str) or compression not in {
        "none",
        "gzip",
        "bzip2",
    }:
        raise UnsupportedDecoderError(
            f"unsupported LIBSVM compression: {compression!r}"
        )
    return compression


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


def _records(value: object, field: str) -> tuple[Mapping[str, Any], ...]:
    return tuple(dict(_object(record, field)) for record in _array(value, field))


def _optional_records(value: object, field: str) -> tuple[Mapping[str, Any], ...]:
    return () if value is None else _records(value, field)


def _data_info(
    dataset: Mapping[str, Any],
    *,
    registry: Registry,
) -> DataInfo:
    source = _string(dataset.get("source"), "dataset.source")
    name = _string(dataset.get("name"), "dataset.name")
    version = _string(dataset.get("version"), "dataset.version")
    representation = dict(
        _object(dataset.get("representation"), "dataset.representation")
    )
    expect = _object(representation.get("expect"), "representation.expect")
    return DataInfo(
        dataset_id=f"{source}:{name}@{version}",
        source=source,
        name=name,
        version=version,
        registry_release=registry.release,
        registry_index_sha256=registry.index_sha256,
        title=_string(dataset.get("title"), "dataset.title"),
        description=_string(dataset.get("description"), "dataset.description"),
        modality=_string(dataset.get("modality"), "dataset.modality"),
        provenance=dict(_object(dataset.get("provenance"), "dataset.provenance")),
        license=dict(_object(dataset.get("license"), "dataset.license")),
        artifacts=tuple(dict(artifact) for artifact in _artifacts(dataset)),
        representation=representation,
        expected_components=_records(
            expect.get("components"), "representation.expect.components"
        ),
        verification_records=_records(
            expect.get("verification"), "representation.expect.verification"
        ),
        related=_optional_records(dataset.get("related"), "dataset.related"),
        tasks=_optional_records(dataset.get("tasks"), "dataset.tasks"),
    )


def data_info(
    name: str,
    *,
    source: str,
    version: str | None = None,
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
) -> DataInfo:
    """Return registry metadata for the version selected by fetch resolution.

    This operation retrieves only the selected registry index. An explicit
    registry overrides session and project selection, and ``offline=True``
    permits a bundled or verified cached index without network requests.
    """

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    selected_registry = registry if registry is not None else active_registry()
    index = _load_registry(selected_registry, cache_root, offline=offline)
    dataset = resolve_dataset(index, source=source, name=name, version=version)
    return _data_info(dataset, registry=selected_registry)


def list_data(
    *,
    registry: Registry | None = None,
    cache_dir: Pathish | None = None,
    offline: bool = False,
) -> tuple[DataInfo, ...]:
    """List every dataset version in the selected immutable registry release."""

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    selected_registry = registry if registry is not None else active_registry()
    index = _load_registry(selected_registry, cache_root, offline=offline)
    datasets = []
    for raw_dataset in _array(index.get("datasets"), "registry.datasets"):
        candidate = _object(raw_dataset, "registry dataset")
        source = _string(candidate.get("source"), "dataset.source")
        name = _string(candidate.get("name"), "dataset.name")
        version = _string(candidate.get("version"), "dataset.version")
        datasets.append(
            resolve_dataset(index, source=source, name=name, version=version)
        )
    return tuple(
        _data_info(dataset, registry=selected_registry) for dataset in datasets
    )


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


def _verification_record(
    index: Mapping[str, Any],
    dataset: Mapping[str, Any],
    expect: Mapping[str, Any],
) -> Mapping[str, Any]:
    identity = {
        "source": _string(dataset.get("source"), "dataset.source"),
        "name": _string(dataset.get("name"), "dataset.name"),
        "version": _string(dataset.get("version"), "dataset.version"),
    }
    revoked: list[Mapping[str, Any]] = []
    for raw_erratum in _array(index.get("errata", ()), "registry.errata"):
        erratum = _object(raw_erratum, "registry erratum")
        if erratum.get("dataset") != identity:
            continue
        target = _object(erratum.get("target"), "erratum.target")
        if target.get("kind") == "verification":
            revoked.append(_object(erratum.get("original"), "erratum.original"))

    records = _array(expect.get("verification"), "representation.expect.verification")
    for raw_record in records:
        record = _object(raw_record, "verification record")
        if (
            record.get("canonical_form") == 1
            and record.get("algorithm") == "sha256"
            and record not in revoked
        ):
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
    return_info: bool,
) -> DatasetData | FetchResult: ...


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
    if decoder_version != 1 or decoder not in {
        "delimited-text",
        "libsvm",
        "libsvm-split",
    }:
        raise UnsupportedDecoderError(
            "the Python client supports delimited-text, LIBSVM, and "
            "LIBSVM split version 1"
        )

    roles = ("train", "test") if decoder == "libsvm-split" else ("data",)
    artifacts = _artifacts_for_representation(dataset, representation, roles)
    options = _object(representation.get("options"), "representation.options")
    compressions: tuple[str, ...]
    if decoder == "delimited-text":
        artifact = artifacts[0]
        artifact_format = artifact.get("format")
        compression = artifact.get("compression")
        if artifact_format not in {"csv", "tsv"}:
            raise UnsupportedDecoderError(
                "delimited-text requires a CSV or TSV artifact"
            )
        expected_delimiter = "," if artifact_format == "csv" else "\t"
        if options.get("delimiter") != expected_delimiter:
            raise UnsupportedDecoderError("artifact format and delimiter disagree")
        if not isinstance(compression, str) or compression not in {
            "none",
            "gzip",
            "bzip2",
        }:
            raise UnsupportedDecoderError(
                f"unsupported delimited-text compression: {compression!r}"
            )
        compressions = (compression,)
    else:
        compressions = tuple(_libsvm_compression(artifact) for artifact in artifacts)
    with ExitStack() as stack:
        artifact_paths = tuple(
            stack.enter_context(
                _retrieve_artifact_lease(artifact, cache_root, offline=offline)
            )
            for artifact in artifacts
        )
        decoded: DecodedTable | DecodedSparseDataset | DecodedSparseDatasetSplit
        if decoder == "delimited-text":
            decoded = decode_delimited_text(
                artifact_paths[0], options, compression=compressions[0]
            )
        elif decoder == "libsvm":
            decoded = decode_libsvm(
                artifact_paths[0], options, compression=compressions[0]
            )
        else:
            decoded = decode_libsvm_split(
                artifact_paths[0],
                artifact_paths[1],
                options,
                train_compression=compressions[0],
                test_compression=compressions[1],
            )
    canonical_form: int | None = None
    canonical_digest: str | None = None
    verification: Literal["artifact", "decoded"] = "artifact"
    if verify_decoded:
        expect = _object(representation.get("expect"), "representation.expect")
        _validate_components(
            decoded.components,
            _array(expect.get("components"), "representation.expect.components"),
        )
        record = _verification_record(index, dataset, expect)
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
    info = FetchInfo(
        dataset_id=dataset_id,
        registry_release=selected_registry.release,
        registry_index_sha256=selected_registry.index_sha256,
        artifact_digests={
            _string(artifact.get("name"), "artifact name"): _string(
                artifact.get("sha256"), "artifact SHA-256"
            )
            for artifact in artifacts
        },
        verification=verification,
        canonical_form=canonical_form,
        canonical_digest=canonical_digest,
    )
    if return_info:
        return FetchResult(data=decoded.data, info=info)
    return decoded.data
