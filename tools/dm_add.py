"""Draft validated dataset manifests from retrieved and decoded artifacts."""

from __future__ import annotations

import argparse
import bz2
import copy
import gzip
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import dm_index
import numpy as np
import yaml

from datamonger._cache import DownloadedFile, download_unverified
from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
from datamonger._errors import DatamongerError
from datamonger._models import (
    DecodedSparseDataset,
    DecodedSparseDatasetSplit,
    DecodedTable,
    LogicalComponent,
    LogicalDenseMatrix,
    LogicalSparseMatrix,
    LogicalValueComponent,
)

ROOT = Path(__file__).resolve().parents[1]
_DERIVED_ARTIFACT_FIELDS = ("size", "sha256")
_SUPPORTED_COMPRESSIONS = {"none", "gzip", "bzip2"}
_SUPPORTED_DECODERS = {"delimited-text", "libsvm", "libsvm-split"}
_SAMPLE_ROWS = 3
_SPARSE_SAMPLE_VALUES = 8
_SCALAR_LIMIT = 80

Decoded = DecodedTable | DecodedSparseDataset | DecodedSparseDatasetSplit


class _BinaryReader(Protocol):
    def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class AuthoringResult:
    """A completed manifest and its bounded human-review report."""

    manifest: dict[str, Any]
    report: str


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object with string keys")
    return cast(dict[str, Any], value)


def _sequence(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _require_fields(record: Mapping[str, Any], fields: set[str], label: str) -> None:
    missing = fields - set(record)
    if missing:
        raise ValueError(f"{label} is missing required fields: {sorted(missing)}")


def _prepare_draft(source: Mapping[str, Any], retrieved_at: date) -> dict[str, Any]:
    manifest = copy.deepcopy(dict(source))
    _require_fields(
        manifest,
        {
            "schema_version",
            "source",
            "name",
            "version",
            "title",
            "description",
            "modality",
            "provenance",
            "license",
            "artifacts",
            "representation",
        },
        "manifest draft",
    )

    provenance = _mapping(manifest["provenance"], "provenance")
    if "retrieved_at" not in provenance:
        provenance["retrieved_at"] = retrieved_at.isoformat()

    artifacts = _sequence(manifest["artifacts"], "artifacts")
    if not artifacts:
        raise ValueError("artifacts must contain at least one artifact")
    names: set[str] = set()
    for index, raw_artifact in enumerate(artifacts):
        artifact = _mapping(raw_artifact, f"artifacts[{index}]")
        _require_fields(
            artifact,
            {"name", "format", "compression", "distribution", "downloads"},
            f"artifacts[{index}]",
        )
        name = _string(artifact["name"], f"artifacts[{index}].name")
        if name in names:
            raise ValueError(f"artifact names must be unique: {name!r}")
        names.add(name)
        compression = _string(artifact["compression"], f"artifact {name} compression")
        if compression not in _SUPPORTED_COMPRESSIONS:
            raise ValueError(
                f"artifact {name} has unsupported compression {compression!r}"
            )
        if artifact["distribution"] == "metadata-only":
            raise ValueError(f"artifact {name} is metadata-only and cannot be authored")
        downloads = _sequence(artifact["downloads"], f"artifact {name} downloads")
        if not downloads:
            raise ValueError(
                f"artifact {name} must have at least one download location"
            )
        for download_index, raw_download in enumerate(downloads):
            download = _mapping(
                raw_download, f"artifact {name} downloads[{download_index}]"
            )
            _string(download.get("url"), f"artifact {name} download URL")

    representation = _mapping(manifest["representation"], "representation")
    _require_fields(
        representation,
        {"decoder", "decoder_version", "inputs", "options"},
        "representation",
    )
    decoder = _string(representation["decoder"], "representation.decoder")
    if decoder not in _SUPPORTED_DECODERS or representation["decoder_version"] != 1:
        raise ValueError(
            "dm-add supports delimited-text, libsvm, and libsvm-split version 1"
        )
    inputs = _mapping(representation["inputs"], "representation.inputs")
    roles = {"train", "test"} if decoder == "libsvm-split" else {"data"}
    if set(inputs) != roles:
        raise ValueError(f"representation inputs must be exactly {sorted(roles)}")
    for role, raw_artifact_name in inputs.items():
        artifact_name = _string(raw_artifact_name, f"representation.inputs.{role}")
        if artifact_name not in names:
            raise ValueError(
                f"representation input {role!r} refers to unknown artifact "
                f"{artifact_name!r}"
            )
    _mapping(representation["options"], "representation.options")
    return manifest


def _detected_compression(path: Path) -> str:
    with path.open("rb") as source:
        prefix = source.read(4)
    if prefix.startswith(b"\x1f\x8b"):
        return "gzip"
    if len(prefix) == 4 and prefix[:3] == b"BZh" and prefix[3:4] in b"123456789":
        return "bzip2"
    return "none"


def _consume(source: _BinaryReader) -> None:
    while source.read(1024 * 1024):
        pass


def _validate_file_compression(
    path: Path, compression: str, artifact_name: str
) -> None:
    try:
        if compression == "gzip":
            with gzip.open(path, "rb") as source:
                _consume(source)
        elif compression == "bzip2":
            with bz2.open(path, "rb") as source:
                _consume(source)
    except (EOFError, OSError) as error:
        raise ValueError(
            f"artifact {artifact_name} contains invalid {compression} data: {error}"
        ) from error


def _check_compression(
    downloaded: DownloadedFile, declared: str, artifact_name: str, url: str
) -> None:
    actual = _detected_compression(downloaded.path)
    if actual != declared:
        if (
            declared == "gzip"
            and actual == "none"
            and downloaded.content_coding in {"gzip", "x-gzip"}
        ):
            raise ValueError(
                f"artifact {artifact_name} from {url} declares gzip compression, "
                f"but HTTP Content-Encoding removed it; this is a compressed-artifact "
                "compression hazard"
            )
        raise ValueError(
            f"artifact {artifact_name} declares compression {declared!r}, "
            f"but {url} is actually {actual}"
        )
    _validate_file_compression(downloaded.path, declared, artifact_name)


def _matching_derived(record: Mapping[str, Any], field: str, expected: object) -> None:
    if field not in record:
        return
    actual = record[field]
    if type(actual) is not type(expected) or actual != expected:
        name = _string(record.get("name"), "artifact name")
        raise ValueError(
            f"artifact {name} {field} does not match the retrieved bytes: "
            f"expected {actual!r}, received {expected!r}"
        )


def _with_artifact_derivatives(
    artifact: Mapping[str, Any], downloaded: DownloadedFile
) -> dict[str, Any]:
    _matching_derived(artifact, "size", downloaded.size)
    _matching_derived(artifact, "sha256", downloaded.sha256)
    result: dict[str, Any] = {}
    for key, value in artifact.items():
        if key in _DERIVED_ARTIFACT_FIELDS:
            continue
        result[key] = value
        if key == "compression":
            result["size"] = downloaded.size
            result["sha256"] = downloaded.sha256
    return result


def _retrieve_artifacts(
    manifest: dict[str, Any], directory: Path
) -> dict[str, DownloadedFile]:
    selected: dict[str, DownloadedFile] = {}
    completed_artifacts: list[dict[str, Any]] = []
    for raw_artifact in _sequence(manifest["artifacts"], "artifacts"):
        artifact = _mapping(raw_artifact, "artifact")
        name = _string(artifact["name"], "artifact.name")
        declared = _string(artifact["compression"], f"artifact {name} compression")
        first: DownloadedFile | None = None
        for raw_download in _sequence(
            artifact["downloads"], f"artifact {name} downloads"
        ):
            download = _mapping(raw_download, f"artifact {name} download")
            url = _string(download.get("url"), f"artifact {name} download URL")
            current = download_unverified(directory=directory, url=url)
            _check_compression(current, declared, name, url)
            if first is None:
                first = current
            elif (current.size, current.sha256) != (first.size, first.sha256):
                raise ValueError(
                    f"artifact {name} from {url} does not match the other locations"
                )
        if first is None:  # pragma: no cover - draft validation rejects this first.
            raise ValueError(f"artifact {name} has no download locations")
        selected[name] = first
        completed_artifacts.append(_with_artifact_derivatives(artifact, first))
    manifest["artifacts"] = completed_artifacts
    return selected


def _decode(
    manifest: Mapping[str, Any], artifacts: Mapping[str, DownloadedFile]
) -> Decoded:
    representation = _mapping(manifest["representation"], "representation")
    decoder = _string(representation["decoder"], "representation.decoder")
    inputs = _mapping(representation["inputs"], "representation.inputs")
    options = _mapping(representation["options"], "representation.options")

    def selected(role: str) -> tuple[Path, str]:
        artifact_name = _string(inputs[role], f"representation.inputs.{role}")
        artifact_records = _sequence(manifest["artifacts"], "artifacts")
        artifact = next(
            _mapping(raw, "artifact")
            for raw in artifact_records
            if _mapping(raw, "artifact").get("name") == artifact_name
        )
        compression = _string(
            artifact["compression"], f"artifact {artifact_name} compression"
        )
        return artifacts[artifact_name].path, compression

    if decoder == "delimited-text":
        path, compression = selected("data")
        return decode_delimited_text(path, options, compression=compression)
    if decoder == "libsvm":
        path, compression = selected("data")
        return decode_libsvm(path, options, compression=compression)
    train_path, train_compression = selected("train")
    test_path, test_compression = selected("test")
    return decode_libsvm_split(
        train_path,
        test_path,
        options,
        train_compression=train_compression,
        test_compression=test_compression,
    )


def _component_record(component: LogicalValueComponent) -> dict[str, Any]:
    if isinstance(component, LogicalComponent):
        return {
            "name": component.name,
            "kind": "vector",
            "type": component.logical_type,
            "length": len(component.values),
        }
    if isinstance(component, LogicalSparseMatrix):
        kind = "sparse_matrix"
    elif isinstance(component, LogicalDenseMatrix):
        kind = "dense_matrix"
    else:  # pragma: no cover - the type union is exhaustive.
        raise TypeError(f"unsupported logical component {type(component).__name__}")
    return {
        "name": component.name,
        "kind": kind,
        "type": component.logical_type,
        "rows": component.rows,
        "columns": component.columns,
    }


def _expectation(components: Sequence[LogicalValueComponent]) -> dict[str, Any]:
    return {
        "components": [_component_record(component) for component in components],
        "verification": [
            {
                "canonical_form": 1,
                "algorithm": "sha256",
                "digest": canonical_sha256(components),
            }
        ],
    }


def _scalar(value: object) -> str:
    if isinstance(value, np.generic):
        value = value.item()
    rendered = repr(value)
    if len(rendered) > _SCALAR_LIMIT:
        return rendered[: _SCALAR_LIMIT - 3] + "..."
    return rendered


def _sample_indices(length: int) -> tuple[int, ...]:
    return tuple(
        sorted(
            set(range(min(_SAMPLE_ROWS, length)))
            | set(range(max(0, length - _SAMPLE_ROWS), length))
        )
    )


def _component_report(component: LogicalValueComponent) -> list[str]:
    record = _component_record(component)
    if isinstance(component, LogicalComponent):
        lines = [
            f"  {component.name}: vector {component.logical_type} "
            f"length={record['length']}"
        ]
        samples = []
        for index in _sample_indices(len(component.values)):
            value = (
                _scalar(component.values[index])
                if component.valid[index]
                else "<missing>"
            )
            samples.append(f"{index}={value}")
        lines.append(f"    samples: {', '.join(samples) if samples else '(empty)'}")
        return lines

    lines = [
        f"  {component.name}: {record['kind']} {component.logical_type} "
        f"rows={component.rows} columns={component.columns}"
    ]
    if isinstance(component, LogicalSparseMatrix):
        for row in _sample_indices(component.rows):
            start = int(component.row_offsets[row])
            end = int(component.row_offsets[row + 1])
            pairs = [
                f"{int(component.column_indices[index])}:{_scalar(component.values[index])}"
                for index in range(start, min(end, start + _SPARSE_SAMPLE_VALUES))
            ]
            if end - start > _SPARSE_SAMPLE_VALUES:
                pairs.append("...")
            lines.append(f"    row {row}: {' '.join(pairs) if pairs else '(empty)'}")
    return lines


def _report(
    manifest: Mapping[str, Any], components: Sequence[LogicalValueComponent]
) -> str:
    lines = ["Artifacts:"]
    for raw_artifact in _sequence(manifest["artifacts"], "artifacts"):
        artifact = _mapping(raw_artifact, "artifact")
        lines.append(
            f"  {artifact['name']}: size={artifact['size']} "
            f"sha256={artifact['sha256']} compression={artifact['compression']} "
            f"locations={len(_sequence(artifact['downloads'], 'artifact downloads'))}"
        )
    lines.append("Components:")
    for component in components:
        lines.extend(_component_report(component))
    return "\n".join(lines)


def build(
    draft_path: Path,
    *,
    root: Path | None = None,
    retrieved_at: date | None = None,
) -> AuthoringResult:
    """Complete, decode, and validate one partial manifest draft."""

    source_root = (root or ROOT).resolve()
    draft = dm_index.load_yaml(draft_path)
    retrieval_date = retrieved_at or datetime.now(UTC).date()
    manifest = _prepare_draft(draft, retrieval_date)
    with tempfile.TemporaryDirectory(prefix="dm-add-") as temporary:
        artifacts = _retrieve_artifacts(manifest, Path(temporary))
        decoded = _decode(manifest, artifacts)
        expect = _expectation(decoded.components)
        representation = _mapping(manifest["representation"], "representation")
        if "expect" in representation and representation["expect"] != expect:
            raise ValueError(
                "representation.expect does not match the decoded components and digest"
            )
        representation["expect"] = expect
        dm_index.validate_manifest(manifest, root=source_root)
        report = _report(manifest, decoded.components)
    return AuthoringResult(manifest=manifest, report=report)


def _yaml_bytes(manifest: Mapping[str, Any]) -> bytes:
    rendered = yaml.safe_dump(
        dict(manifest),
        allow_unicode=True,
        sort_keys=False,
        width=88,
    )
    return rendered.encode("utf-8")


def _write_atomic(path: Path, contents: bytes, *, force: bool) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(contents)
            temporary.flush()
            os.fsync(temporary.fileno())
        if force:
            os.replace(temporary_path, path)
        else:
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                raise ValueError(f"output path already exists: {path}") from None
            temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    """Run the manifest-authoring command-line interface."""

    parser = argparse.ArgumentParser(prog="dm-add")
    parser.add_argument("draft", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--force", action="store_true", help="replace an existing output file"
    )
    arguments = parser.parse_args()
    if arguments.force and arguments.output is None:
        parser.error("--force requires --output")

    try:
        if (
            arguments.output is not None
            and arguments.output.exists()
            and not arguments.force
        ):
            raise ValueError(
                f"output path already exists: {arguments.output.resolve()}"
            )
        result = build(arguments.draft)
        contents = _yaml_bytes(result.manifest)
        if arguments.output is None:
            sys.stdout.buffer.write(contents)
        else:
            _write_atomic(arguments.output, contents, force=arguments.force)
        print(result.report, file=sys.stderr)
    except (DatamongerError, OSError, ValueError) as error:
        print(f"dm-add: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
