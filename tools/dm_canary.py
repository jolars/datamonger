"""Re-fetch and decode every dataset in an immutable registry release."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import dm_index

from datamonger._api import _validate_components, _verification_record
from datamonger._cache import DownloadedFile, download_unverified
from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
from datamonger._errors import (
    DatamongerError,
    DecodedIntegrityError,
    RegistryIntegrityError,
    RegistryRetrievalError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
)
from datamonger._models import (
    DecodedSparseDataset,
    DecodedSparseDatasetSplit,
    DecodedTable,
    Registry,
)
from datamonger._registry import validate_registry_selector

ROOT = Path(__file__).resolve().parents[1]

CheckKind = Literal["registry", "location", "dataset"]
Decoded = DecodedTable | DecodedSparseDataset | DecodedSparseDatasetSplit


@dataclass(frozen=True)
class CanaryCheck:
    """The outcome of one registry, location, or decoded-data check."""

    kind: CheckKind
    ok: bool
    message: str
    dataset_id: str | None = None
    artifact_name: str | None = None
    url: str | None = None

    def label(self) -> str:
        """Render the check target as a compact Markdown label."""

        if self.kind == "registry":
            return "registry index"
        if self.kind == "dataset":
            return f"dataset `{self.dataset_id}`"
        return (
            f"dataset `{self.dataset_id}`, artifact `{self.artifact_name}`, "
            f"location <{self.url}>"
        )


@dataclass(frozen=True)
class CanaryResult:
    """All checks from one uncached canary run."""

    release: str
    checks: tuple[CanaryCheck, ...]
    implementation: str = "Python reference client"

    @property
    def ok(self) -> bool:
        """Return whether every check passed."""

        return all(check.ok for check in self.checks)

    def render_markdown(self) -> str:
        """Render a report suitable for a terminal or GitHub issue."""

        passed = sum(check.ok for check in self.checks)
        failed = len(self.checks) - passed
        status = "PASSED" if self.ok else "FAILED"
        lines = [
            f"# Datamonger canary: {status}",
            "",
            f"- Release: `{self.release}`",
            f"- Implementation: {self.implementation}",
            f"- Checks: {passed} passed, {failed} failed",
        ]
        failures = [check for check in self.checks if not check.ok]
        if failures:
            lines.extend(("", "## Failures", ""))
            lines.extend(f"- {check.label()}: {check.message}" for check in failures)
        lines.extend(("", "## Checks", ""))
        lines.extend(
            f"- {'PASS' if check.ok else 'FAIL'} — {check.label()}: {check.message}"
            for check in self.checks
        )
        return "\n".join(lines) + "\n"


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise UnsupportedRegistryError(f"{field} must be an object with string keys")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise UnsupportedRegistryError(f"{field} must be an array")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise UnsupportedRegistryError(f"{field} must be a nonempty string")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnsupportedRegistryError(f"{field} must be a nonnegative integer")
    return value


def _read_selector(path: Path) -> Registry:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read registry selector {path}: {error}") from error
    selector = _mapping(value, "registry selector")
    expected_fields = {"release", "index_sha256", "index_url"}
    if set(selector) != expected_fields:
        raise ValueError(
            "registry selector must contain exactly release, index_sha256, "
            "and index_url"
        )
    registry = Registry(
        release=cast(str, selector["release"]),
        index_sha256=cast(str, selector["index_sha256"]),
        index_url=cast(str, selector["index_url"]),
    )
    validate_registry_selector(registry)
    return registry


def _read_index(path: Path, registry: Registry, root: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UnsupportedRegistryError(
            f"verified registry index is invalid JSON: {error}"
        ) from error
    index = _mapping(value, "registry index")
    required = {"schema_version", "release", "defaults", "datasets"}
    allowed = required | {"errata"}
    if not required <= set(index) or not set(index) <= allowed:
        raise UnsupportedRegistryError(
            "registry index has missing or unsupported top-level fields"
        )
    if index.get("schema_version") != 1:
        raise UnsupportedRegistryError(
            f"unsupported registry schema {index.get('schema_version')!r}"
        )
    if index.get("release") != registry.release:
        raise UnsupportedRegistryError(
            f"selected release {registry.release!r} does not match embedded release "
            f"{index.get('release')!r}"
        )
    _sequence(index.get("defaults"), "registry defaults")
    _sequence(index.get("errata", ()), "registry errata")
    identities: set[tuple[str, str, str]] = set()
    for raw_dataset in _sequence(index.get("datasets"), "registry datasets"):
        dataset = _mapping(raw_dataset, "registry dataset")
        dm_index.validate_manifest(dataset, root=root)
        identity = _identity(dataset)
        if identity in identities:
            raise UnsupportedRegistryError(
                f"registry contains duplicate dataset {_dataset_id(dataset)}"
            )
        identities.add(identity)
    return index


def _identity(dataset: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        _string(dataset.get("source"), "dataset.source"),
        _string(dataset.get("name"), "dataset.name"),
        _string(dataset.get("version"), "dataset.version"),
    )


def _dataset_id(dataset: Mapping[str, Any]) -> str:
    source, name, version = _identity(dataset)
    return f"{source}:{name}@{version}"


def _detected_compression(path: Path) -> str:
    with path.open("rb") as source:
        prefix = source.read(4)
    if prefix.startswith(b"\x1f\x8b"):
        return "gzip"
    if len(prefix) == 4 and prefix[:3] == b"BZh" and prefix[3:4] in b"123456789":
        return "bzip2"
    return "none"


def _artifact_mismatch(
    downloaded: DownloadedFile,
    artifact: Mapping[str, Any],
    url: str,
) -> str | None:
    name = _string(artifact.get("name"), "artifact name")
    compression = _string(artifact.get("compression"), "artifact compression")
    actual_compression = _detected_compression(downloaded.path)
    if (
        compression == "gzip"
        and actual_compression == "none"
        and downloaded.content_coding in {"gzip", "x-gzip"}
    ):
        return (
            f"HTTP Content-Encoding removed declared gzip compression from {url}; "
            f"artifact {name!r} has the compressed-artifact compression hazard"
        )
    expected_size = _integer(artifact.get("size"), "artifact size")
    if downloaded.size != expected_size:
        return f"size mismatch: expected {expected_size}, received {downloaded.size}"
    expected_digest = _string(artifact.get("sha256"), "artifact SHA-256")
    if downloaded.sha256 != expected_digest:
        return (
            f"SHA-256 mismatch: expected {expected_digest}, "
            f"received {downloaded.sha256}"
        )
    return None


def _artifact_records(
    dataset: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        _mapping(raw_artifact, "dataset artifact")
        for raw_artifact in _sequence(dataset.get("artifacts"), "dataset artifacts")
    )


def _decode_dataset(
    index: Mapping[str, Any],
    dataset: Mapping[str, Any],
    artifact_paths: Mapping[str, Path],
) -> str:
    representation = _mapping(dataset.get("representation"), "dataset representation")
    decoder = representation.get("decoder")
    if representation.get("decoder_version") != 1 or decoder not in {
        "delimited-text",
        "libsvm",
        "libsvm-split",
    }:
        raise UnsupportedDecoderError(
            f"unsupported decoder {decoder!r} version "
            f"{representation.get('decoder_version')!r}"
        )
    roles = ("train", "test") if decoder == "libsvm-split" else ("data",)
    inputs = _mapping(representation.get("inputs"), "representation inputs")
    if set(inputs) != set(roles):
        raise UnsupportedRegistryError(
            f"representation inputs must be exactly {list(roles)!r}"
        )
    artifacts = {
        _string(artifact.get("name"), "artifact name"): artifact
        for artifact in _artifact_records(dataset)
    }
    selected: list[tuple[Path, Mapping[str, Any]]] = []
    for role in roles:
        artifact_name = _string(inputs.get(role), f"representation input {role}")
        if artifact_name not in artifacts:
            raise UnsupportedRegistryError(
                f"representation input {role!r} refers to unknown artifact "
                f"{artifact_name!r}"
            )
        if artifact_name not in artifact_paths:
            raise DecodedIntegrityError(
                f"no location supplied verified bytes for artifact {artifact_name!r}"
            )
        selected.append((artifact_paths[artifact_name], artifacts[artifact_name]))

    options = _mapping(representation.get("options"), "representation options")
    decoded: Decoded
    if decoder == "delimited-text":
        path, artifact = selected[0]
        decoded = decode_delimited_text(
            path,
            options,
            compression=_string(artifact.get("compression"), "artifact compression"),
        )
    elif decoder == "libsvm":
        path, artifact = selected[0]
        decoded = decode_libsvm(
            path,
            options,
            compression=_string(artifact.get("compression"), "artifact compression"),
        )
    else:
        train_path, train_artifact = selected[0]
        test_path, test_artifact = selected[1]
        decoded = decode_libsvm_split(
            train_path,
            test_path,
            options,
            train_compression=_string(
                train_artifact.get("compression"), "train artifact compression"
            ),
            test_compression=_string(
                test_artifact.get("compression"), "test artifact compression"
            ),
        )

    expect = _mapping(representation.get("expect"), "representation expectation")
    _validate_components(
        decoded.components,
        _sequence(expect.get("components"), "expected components"),
    )
    record = _verification_record(index, dataset, expect)
    expected_digest = _string(record.get("digest"), "canonical digest")
    actual_digest = canonical_sha256(decoded.components)
    if actual_digest != expected_digest:
        raise DecodedIntegrityError(
            f"decoded SHA-256 mismatch: expected {expected_digest}, "
            f"received {actual_digest}"
        )
    return actual_digest


def _registry_failure(registry: Registry, message: str) -> CanaryResult:
    return CanaryResult(
        release=registry.release,
        checks=(CanaryCheck(kind="registry", ok=False, message=message),),
    )


def check(selector_path: Path, *, root: Path | None = None) -> CanaryResult:
    """Run uncached location and decoded-data checks for one release selector."""

    source_root = (root or ROOT).resolve()
    registry = _read_selector(selector_path)
    checks: list[CanaryCheck] = []
    with tempfile.TemporaryDirectory(prefix="dm-canary-") as temporary:
        directory = Path(temporary)
        try:
            downloaded_index = download_unverified(
                directory=directory,
                url=registry.index_url,
                retrieval_error=RegistryRetrievalError,
            )
        except DatamongerError as error:
            return _registry_failure(registry, str(error))
        if downloaded_index.sha256 != registry.index_sha256:
            integrity_error = RegistryIntegrityError(
                "registry index SHA-256 mismatch: "
                f"expected {registry.index_sha256}, "
                f"received {downloaded_index.sha256}"
            )
            return _registry_failure(registry, str(integrity_error))
        try:
            index = _read_index(downloaded_index.path, registry, source_root)
        except (DatamongerError, OSError, ValueError) as error:
            return _registry_failure(registry, str(error))
        checks.append(
            CanaryCheck(
                kind="registry",
                ok=True,
                message=f"verified SHA-256 {registry.index_sha256}",
            )
        )

        for raw_dataset in _sequence(index.get("datasets"), "registry datasets"):
            dataset = _mapping(raw_dataset, "registry dataset")
            dataset_id = _dataset_id(dataset)
            verified_paths: dict[str, Path] = {}
            for artifact in _artifact_records(dataset):
                artifact_name = _string(artifact.get("name"), "artifact name")
                downloads = _sequence(
                    artifact.get("downloads"), "artifact download locations"
                )
                for raw_download in downloads:
                    download = _mapping(raw_download, "artifact download")
                    url = _string(download.get("url"), "artifact download URL")
                    try:
                        downloaded = download_unverified(directory=directory, url=url)
                        mismatch = _artifact_mismatch(downloaded, artifact, url)
                    except (DatamongerError, OSError, ValueError) as error:
                        checks.append(
                            CanaryCheck(
                                kind="location",
                                ok=False,
                                message=str(error),
                                dataset_id=dataset_id,
                                artifact_name=artifact_name,
                                url=url,
                            )
                        )
                        continue
                    if mismatch is not None:
                        checks.append(
                            CanaryCheck(
                                kind="location",
                                ok=False,
                                message=mismatch,
                                dataset_id=dataset_id,
                                artifact_name=artifact_name,
                                url=url,
                            )
                        )
                        continue
                    verified_paths.setdefault(artifact_name, downloaded.path)
                    checks.append(
                        CanaryCheck(
                            kind="location",
                            ok=True,
                            message=(
                                f"served {downloaded.size} registered bytes with "
                                f"SHA-256 {downloaded.sha256}"
                            ),
                            dataset_id=dataset_id,
                            artifact_name=artifact_name,
                            url=url,
                        )
                    )
            try:
                canonical_digest = _decode_dataset(index, dataset, verified_paths)
            except (DatamongerError, OSError, ValueError) as error:
                checks.append(
                    CanaryCheck(
                        kind="dataset",
                        ok=False,
                        message=str(error),
                        dataset_id=dataset_id,
                    )
                )
            else:
                checks.append(
                    CanaryCheck(
                        kind="dataset",
                        ok=True,
                        message=f"verified canonical SHA-256 {canonical_digest}",
                        dataset_id=dataset_id,
                    )
                )
    return CanaryResult(release=registry.release, checks=tuple(checks))


def main() -> int:
    """Run the upstream-verification command-line interface."""

    parser = argparse.ArgumentParser(prog="dm-canary")
    parser.add_argument("selector", type=Path, help="strong registry selector JSON")
    arguments = parser.parse_args()
    try:
        result = check(arguments.selector)
    except (DatamongerError, OSError, ValueError) as error:
        print(f"dm-canary: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(result.render_markdown())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
