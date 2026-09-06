"""Validate registry sources and build deterministic immutable indexes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry as SchemaRegistry
from referencing import Resource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = Path("registry/releases/candidate-0001/release.yaml")

Identity = tuple[str, str, str]


class _UniqueKeyLoader(yaml.SafeLoader):
    """Load the JSON-compatible YAML subset while rejecting duplicate keys."""


def _construct_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as error:
            raise ValueError("YAML mapping keys must be scalar JSON values") from error
        if duplicate:
            raise ValueError(f"duplicate YAML mapping key {key!r}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object with string keys")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be an array")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _json_value(value: object, field: str = "YAML value") -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{field} contains a non-Unicode scalar value") from error
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{field} contains a non-string object key")
            _json_value(item, f"{field}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, item in enumerate(value):
            _json_value(item, f"{field}[{index}]")
        return
    raise ValueError(f"{field} has non-JSON type {type(value).__name__}")


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except yaml.YAMLError as error:
        raise ValueError(f"cannot parse {path}: {error}") from error
    _json_value(value, str(path))
    return _mapping(value, str(path))


def load_yaml(path: Path) -> Mapping[str, Any]:
    """Load one JSON-compatible YAML authoring document."""

    return _load_yaml(path)


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot parse {path}: {error}") from error
    return _mapping(value, str(path))


def _schema_resources(schema_directory: Path) -> tuple[SchemaRegistry, dict[str, Any]]:
    schemas: dict[str, Any] = {}
    registry = SchemaRegistry()
    for path in sorted(schema_directory.glob("*.schema.json")):
        schema = dict(_load_json(path))
        schema_id = _string(schema.get("$id"), f"{path}.$id")
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry, schemas


def _validate_schema(
    value: object,
    schema_name: str,
    schema_directory: Path,
    field: str,
) -> None:
    registry, schemas = _schema_resources(schema_directory)
    try:
        schema = schemas[schema_name]
    except KeyError as missing_error:
        raise ValueError(f"missing schema {schema_name}") from missing_error
    validator = Draft202012Validator(
        schema, registry=registry, format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path)
        suffix = f" at {location}" if location else ""
        raise ValueError(f"{field} violates {schema_name}{suffix}: {error.message}")


def _source_path(root: Path, value: object, field: str) -> Path:
    raw = _string(value, field)
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field} must be a repository-relative path")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"{field} escapes the repository root")
    return path


def _identity(record: Mapping[str, Any], field: str) -> Identity:
    return (
        _string(record.get("source"), f"{field}.source"),
        _string(record.get("name"), f"{field}.name"),
        _string(record.get("version"), f"{field}.version"),
    )


def _unique(records: Sequence[object], field: str, key: str) -> None:
    values: list[str] = []
    for index, raw in enumerate(records):
        record = _mapping(raw, f"{field}[{index}]")
        values.append(_string(record.get(key), f"{field}[{index}].{key}"))
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must have unique {key} values")


def _components(dataset: Mapping[str, Any]) -> Sequence[object]:
    representation = _mapping(dataset.get("representation"), "representation")
    expect = _mapping(representation.get("expect"), "representation.expect")
    return _sequence(expect.get("components"), "representation.expect.components")


def _verification(dataset: Mapping[str, Any]) -> Sequence[object]:
    representation = _mapping(dataset.get("representation"), "representation")
    expect = _mapping(representation.get("expect"), "representation.expect")
    return _sequence(expect.get("verification"), "representation.expect.verification")


def _validate_dataset(dataset: Mapping[str, Any]) -> None:
    identity = ":".join(_identity(dataset, "dataset"))
    artifacts = _sequence(dataset.get("artifacts"), f"{identity}.artifacts")
    _unique(artifacts, f"{identity}.artifacts", "name")
    artifact_records = [_mapping(raw, f"{identity}.artifacts") for raw in artifacts]
    dataset_license = _mapping(dataset.get("license"), f"{identity}.license")
    artifact_by_name = {
        _string(artifact.get("name"), "artifact.name"): artifact
        for artifact in artifact_records
    }

    for artifact in artifact_records:
        distribution = artifact.get("distribution")
        downloads = [
            _mapping(raw, "artifact.download")
            for raw in _sequence(artifact.get("downloads"), "artifact.downloads")
        ]
        _unique(downloads, "artifact.downloads", "url")
        kinds = [download.get("kind") for download in downloads]
        if distribution == "upstream-only" and any(
            kind != "upstream" for kind in kinds
        ):
            raise ValueError("upstream-only artifacts may use only upstream locations")
        if distribution == "mirror" and "mirror" not in kinds:
            raise ValueError("mirror artifacts require a mirror location")
        if distribution == "mirror":
            artifact_license = artifact.get("license")
            license_record = (
                _mapping(artifact_license, "artifact.license")
                if artifact_license is not None
                else dataset_license
            )
            review = {"evidence", "reviewed_by", "reviewed_at"}
            if license_record.get("status") != "known" or not review <= set(
                license_record
            ):
                raise ValueError("mirror artifacts require a reviewed known license")
        if distribution == "metadata-only" and downloads:
            raise ValueError("metadata-only artifacts must not have locations")
        preservation = artifact.get("preservation")
        if (
            isinstance(preservation, Mapping)
            and preservation.get("status") == "durable"
        ):
            required = {"deposit", "evidence", "reviewed_by", "reviewed_at"}
            if not required <= set(preservation):
                raise ValueError(
                    "durable preservation requires complete review metadata"
                )
            if distribution == "metadata-only":
                raise ValueError(
                    "metadata-only artifacts cannot claim durable preservation"
                )

    representation = _mapping(dataset.get("representation"), "representation")
    decoder = _string(representation.get("decoder"), "representation.decoder")
    inputs = _mapping(representation.get("inputs"), "representation.inputs")
    options = _mapping(representation.get("options"), "representation.options")
    if (
        decoder in {"libsvm", "libsvm-split"}
        and options.get("target_name") == "features"
    ):
        raise ValueError("LIBSVM target_name must be distinct from features")
    for input_name, artifact_name in inputs.items():
        if artifact_name not in artifact_by_name:
            raise ValueError(
                f"representation input {input_name!r} refers to unknown artifact "
                f"{artifact_name!r}"
            )

    if decoder == "delimited-text":
        artifact = artifact_by_name[cast(str, inputs["data"])]
        expected_delimiter = "," if artifact.get("format") == "csv" else "\t"
        if artifact.get("format") not in {"csv", "tsv"}:
            raise ValueError("delimited-text requires a CSV or TSV artifact")
        if options.get("delimiter") != expected_delimiter:
            raise ValueError("artifact format and delimiter disagree")
    else:
        for artifact_name in inputs.values():
            if artifact_by_name[cast(str, artifact_name)].get("format") not in {
                "libsvm",
                "svmlight",
            }:
                raise ValueError("LIBSVM decoders require LIBSVM or SVMLight artifacts")

    components = _components(dataset)
    _unique(components, f"{identity}.components", "name")
    component_records = [_mapping(raw, "component") for raw in components]
    component_by_name = {
        _string(component.get("name"), "component.name"): component
        for component in component_records
    }
    for component in component_records:
        if component.get("kind") == "dense_matrix":
            rows = cast(int, component["rows"])
            dense_columns = cast(int, component["columns"])
            if rows * dense_columns > 0xFFFFFFFFFFFFFFFF:
                raise ValueError("dense component element count exceeds uint64")
    verification = _verification(dataset)
    verification_keys = [
        (
            _mapping(raw, "verification").get("canonical_form"),
            _mapping(raw, "verification").get("algorithm"),
            _mapping(raw, "verification").get("digest"),
        )
        for raw in verification
    ]
    if len(verification_keys) != len(set(verification_keys)):
        raise ValueError("verification records must be unique")

    if decoder == "delimited-text":
        columns = [
            _mapping(raw, "column")
            for raw in _sequence(options.get("columns"), "options.columns")
        ]
        _unique(columns, "options.columns", "name")
        expected = [
            (column.get("name"), "vector", column.get("type")) for column in columns
        ]
        actual = [
            (component.get("name"), component.get("kind"), component.get("type"))
            for component in component_records
        ]
        if actual != expected:
            raise ValueError("delimited-text components disagree with declared columns")
        lengths = {component.get("length") for component in component_records}
        if len(lengths) != 1:
            raise ValueError("delimited-text components must have equal lengths")
    elif decoder == "libsvm":
        target = cast(str, options["target_name"])
        expected_names = ["features", target]
        if list(component_by_name) != expected_names:
            raise ValueError("LIBSVM components have the wrong names or order")
        features = component_by_name["features"]
        response = component_by_name[target]
        if (
            features.get("kind") != "sparse_matrix"
            or features.get("type") != "float64"
            or features.get("columns") != options.get("feature_count")
            or response.get("kind") != "vector"
            or response.get("type") != options.get("label_type")
            or response.get("length") != features.get("rows")
        ):
            raise ValueError("LIBSVM component shapes disagree with decoder options")
    elif decoder == "libsvm-split":
        target = cast(str, options["target_name"])
        expected_names = [
            "train_features",
            f"train_{target}",
            "test_features",
            f"test_{target}",
        ]
        if list(component_by_name) != expected_names:
            raise ValueError("LIBSVM split components have the wrong names or order")
        for split in ("train", "test"):
            features = component_by_name[f"{split}_features"]
            response = component_by_name[f"{split}_{target}"]
            if (
                features.get("kind") != "sparse_matrix"
                or features.get("type") != "float64"
                or features.get("columns") != options.get("feature_count")
                or response.get("kind") != "vector"
                or response.get("type") != options.get("label_type")
                or response.get("length") != features.get("rows")
            ):
                raise ValueError(
                    f"LIBSVM {split} component shapes disagree with decoder options"
                )

    tasks = _sequence(dataset.get("tasks", []), f"{identity}.tasks")
    _unique(tasks, f"{identity}.tasks", "name")
    for raw_task in tasks:
        task = _mapping(raw_task, "task")
        role_records = [task]
        raw_splits = task.get("splits")
        if isinstance(raw_splits, Mapping):
            for raw_roles in raw_splits.values():
                role_records.append(_mapping(raw_roles, "task split"))
        for roles in role_records:
            role_features = roles.get("features")
            feature_names = (
                role_features
                if isinstance(role_features, Sequence)
                and not isinstance(role_features, str)
                else [role_features]
            )
            role_target = roles.get("target")
            if role_target is not None and role_target in feature_names:
                raise ValueError("task feature and target roles must be distinct")
            for name in [*feature_names, role_target]:
                if name is not None and name not in component_by_name:
                    raise ValueError(f"task refers to unknown component {name!r}")


def validate_manifest(dataset: Mapping[str, Any], *, root: Path | None = None) -> None:
    """Validate one complete manifest against its schema and semantic rules."""

    source_root = (root or ROOT).resolve()
    _validate_schema(
        dataset,
        "manifest-v1.schema.json",
        source_root / "spec" / "schema",
        "manifest",
    )
    _validate_dataset(dataset)


def _identity_projection(dataset: Mapping[str, Any]) -> object:
    artifacts = []
    for raw in _sequence(dataset.get("artifacts"), "artifacts"):
        artifact = _mapping(raw, "artifact")
        artifacts.append(
            {
                key: artifact[key]
                for key in ("name", "size", "sha256", "format", "compression")
            }
        )
    artifacts.sort(key=lambda artifact: cast(str, artifact["name"]))
    representation = _mapping(dataset.get("representation"), "representation")
    return {
        "source": dataset["source"],
        "name": dataset["name"],
        "version": dataset["version"],
        "artifacts": artifacts,
        "representation": {
            key: representation[key]
            for key in ("decoder", "decoder_version", "inputs", "options")
        },
    }


def _record_map(records: Sequence[object], field: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for raw in records:
        record = _mapping(raw, field)
        name = _string(record.get("name"), f"{field}.name")
        result[name] = record
    return result


def _matching_component_erratum(
    errata: Sequence[object],
    release: str,
    identity: Identity,
    original: object,
    replacement: object,
) -> bool:
    for raw in errata:
        erratum = _mapping(raw, "erratum")
        dataset = _mapping(erratum.get("dataset"), "erratum.dataset")
        target = _mapping(erratum.get("target"), "erratum.target")
        if (
            erratum.get("release") == release
            and _identity(dataset, "erratum.dataset") == identity
            and target.get("kind") == "component"
            and erratum.get("original") == original
            and erratum.get("replacement") == replacement
        ):
            return True
    return False


def _compare_dataset(
    current: Mapping[str, Any],
    previous: Mapping[str, Any],
    previous_release: str,
    errata: Sequence[object],
) -> None:
    identity = _identity(current, "dataset")
    label = f"{identity[0]}:{identity[1]}@{identity[2]}"
    if _identity_projection(current) != _identity_projection(previous):
        raise ValueError(f"{label} changes identity-bearing fields")

    previous_tasks = _record_map(_sequence(previous.get("tasks", []), "tasks"), "task")
    current_tasks = _record_map(_sequence(current.get("tasks", []), "tasks"), "task")
    for name, task in previous_tasks.items():
        if current_tasks.get(name) != task:
            raise ValueError(f"{label} mutates or removes task {name!r}")

    previous_components = list(_components(previous))
    current_components = list(_components(current))
    if len(previous_components) != len(current_components):
        raise ValueError(f"{label} changes its component set")
    for old, new in zip(previous_components, current_components, strict=True):
        if old != new and not _matching_component_erratum(
            errata, previous_release, identity, old, new
        ):
            raise ValueError(f"{label} mutates a component without an erratum")

    old_verification = list(_verification(previous))
    new_verification = list(_verification(current))
    if new_verification[: len(old_verification)] != old_verification:
        raise ValueError(f"{label} verification records are not append-only")


def _validate_errata(
    errata: Sequence[object],
    datasets: Mapping[Identity, Mapping[str, Any]],
    histories: Sequence[Mapping[str, Any]],
) -> None:
    _unique(errata, "errata", "id")
    history_by_release = {
        _string(history.get("release"), "history.release"): history
        for history in histories
    }
    for raw in errata:
        erratum = _mapping(raw, "erratum")
        release = _string(erratum.get("release"), "erratum.release")
        try:
            history = history_by_release[release]
        except KeyError as error:
            raise ValueError(
                f"erratum refers to unknown release {release!r}"
            ) from error
        target_identity = _identity(
            _mapping(erratum.get("dataset"), "erratum.dataset"), "erratum.dataset"
        )
        old_datasets = {
            _identity(_mapping(raw_dataset, "dataset"), "dataset"): _mapping(
                raw_dataset, "dataset"
            )
            for raw_dataset in _sequence(history.get("datasets"), "history.datasets")
        }
        if target_identity not in old_datasets or target_identity not in datasets:
            raise ValueError(
                "erratum dataset must exist in affected and current releases"
            )
        old = old_datasets[target_identity]
        current = datasets[target_identity]
        target = _mapping(erratum.get("target"), "erratum.target")
        original = erratum.get("original")
        replacement = erratum.get("replacement")
        if target.get("kind") == "component":
            name = target.get("name")
            old_components = _record_map(_components(old), "component")
            current_components = _record_map(_components(current), "component")
            if old_components.get(cast(str, name)) != original:
                raise ValueError(
                    "erratum original does not match the affected component"
                )
            if current_components.get(cast(str, name)) != replacement:
                raise ValueError(
                    "erratum replacement does not match the current component"
                )
        else:
            key = (target.get("canonical_form"), target.get("algorithm"))

            def records(
                dataset: Mapping[str, Any],
            ) -> dict[tuple[object, object], object]:
                return {
                    (
                        _mapping(raw_record, "verification").get("canonical_form"),
                        _mapping(raw_record, "verification").get("algorithm"),
                    ): raw_record
                    for raw_record in _verification(dataset)
                }

            old_verification = records(old)
            current_verification = list(_verification(current))
            if old_verification.get(key) != original:
                raise ValueError(
                    "erratum original does not match the verification record"
                )
            replacement_record = _mapping(replacement, "erratum.replacement")
            replacement_key = (
                replacement_record.get("canonical_form"),
                replacement_record.get("algorithm"),
            )
            if replacement_key != key:
                raise ValueError(
                    "verification erratum replacement must match the target key"
                )
            if (
                original not in current_verification
                or replacement not in current_verification
            ):
                raise ValueError(
                    "verification errata must retain the original and append its "
                    "replacement"
                )


def _validate_active_verification(
    errata: Sequence[object],
    datasets: Mapping[Identity, Mapping[str, Any]],
) -> None:
    revoked: dict[Identity, list[object]] = {}
    for raw in errata:
        erratum = _mapping(raw, "erratum")
        target = _mapping(erratum.get("target"), "erratum.target")
        if target.get("kind") != "verification":
            continue
        identity = _identity(
            _mapping(erratum.get("dataset"), "erratum.dataset"),
            "erratum.dataset",
        )
        revoked.setdefault(identity, []).append(erratum.get("original"))

    for identity, dataset in datasets.items():
        records_by_key: dict[tuple[object, object], list[object]] = {}
        for raw in _verification(dataset):
            record = _mapping(raw, "verification")
            key = (record.get("canonical_form"), record.get("algorithm"))
            records_by_key.setdefault(key, []).append(raw)
        for key, records in records_by_key.items():
            active = [
                record for record in records if record not in revoked.get(identity, [])
            ]
            if len(active) != 1:
                label = f"{identity[0]}:{identity[1]}@{identity[2]}"
                raise ValueError(
                    f"{label} must have one active verification record for {key!r}"
                )


def _history_indexes(
    release_path: Path, current_sequence: int
) -> list[Mapping[str, Any]]:
    releases_root = release_path.parent.parent
    if releases_root.name != "releases":
        return []
    histories: list[Mapping[str, Any]] = []
    sequences: dict[int, Path] = {}
    for source_path in sorted(releases_root.glob("*/release.yaml")):
        source = _load_yaml(source_path)
        sequence = source.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ValueError(f"{source_path} has an invalid release sequence")
        if sequence in sequences:
            raise ValueError(
                f"release sequence {sequence} is shared by {sequences[sequence]} "
                f"and {source_path}"
            )
        sequences[sequence] = source_path
        if sequence < current_sequence:
            index_path = source_path.parent / "index.json"
            if not index_path.is_file():
                raise ValueError(f"earlier release is missing its index: {index_path}")
            histories.append(_load_json(index_path))
    return histories


def _json_bytes(value: object) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded.encode("utf-8") + b"\n"


def build(release_path: Path, *, root: Path | None = None) -> tuple[bytes, bytes]:
    """Return a validated release's deterministic index and selector bytes."""

    source_root = (root or ROOT).resolve()
    schema_directory = source_root / "spec" / "schema"
    release_path = release_path.resolve()
    if not release_path.is_relative_to(source_root):
        raise ValueError("release source must be inside the repository root")
    release_record = _load_yaml(release_path)
    _validate_schema(
        release_record,
        "release-source-v1.schema.json",
        schema_directory,
        str(release_path),
    )
    release = _string(release_record.get("release"), "release")
    sequence = cast(int, release_record["sequence"])

    datasets = [
        _load_yaml(_source_path(source_root, path, "manifest path"))
        for path in _sequence(release_record.get("manifests"), "manifests")
    ]
    for dataset in datasets:
        validate_manifest(dataset, root=source_root)
    identities = [_identity(dataset, "dataset") for dataset in datasets]
    if len(identities) != len(set(identities)):
        raise ValueError("dataset identifiers must be unique")
    dataset_by_identity = dict(zip(identities, datasets, strict=True))

    defaults = [
        _mapping(value, "default")
        for value in _sequence(release_record.get("defaults"), "defaults")
    ]
    default_identities = [_identity(default, "default") for default in defaults]
    default_keys = [(source, name) for source, name, _ in default_identities]
    if len(default_keys) != len(set(default_keys)):
        raise ValueError("each dataset may declare at most one default version")
    unknown_defaults = set(default_identities) - set(identities)
    if unknown_defaults:
        raise ValueError(f"defaults refer to unknown datasets: {unknown_defaults}")

    errata = [
        _load_yaml(_source_path(source_root, path, "erratum path"))
        for path in _sequence(release_record.get("errata", []), "errata")
    ]
    for erratum in errata:
        _validate_schema(erratum, "erratum-v1.schema.json", schema_directory, "erratum")

    histories = _history_indexes(release_path, sequence)
    for history in histories:
        _validate_schema(
            history,
            "index-v1.schema.json",
            schema_directory,
            "historical index",
        )
    history_releases = [
        _string(history.get("release"), "history.release") for history in histories
    ]
    if len(history_releases) != len(set(history_releases)):
        raise ValueError("historical release identifiers must be unique")
    if release in history_releases:
        raise ValueError(f"release identifier {release!r} is already immutable")
    _validate_errata(errata, dataset_by_identity, histories)
    _validate_active_verification(errata, dataset_by_identity)
    current_errata = {
        _string(erratum.get("id"), "erratum.id"): erratum for erratum in errata
    }
    for history in histories:
        previous_release = _string(history.get("release"), "history.release")
        for raw_erratum in _sequence(history.get("errata", []), "history.errata"):
            old_erratum = _mapping(raw_erratum, "historical erratum")
            erratum_id = _string(old_erratum.get("id"), "historical erratum.id")
            if current_errata.get(erratum_id) != old_erratum:
                raise ValueError(
                    f"release {release!r} mutates or removes erratum {erratum_id!r}"
                )
        previous_datasets = {
            _identity(_mapping(raw, "dataset"), "dataset"): _mapping(raw, "dataset")
            for raw in _sequence(history.get("datasets"), "history.datasets")
        }
        for identity, dataset in dataset_by_identity.items():
            if identity in previous_datasets:
                _compare_dataset(
                    dataset, previous_datasets[identity], previous_release, errata
                )

    index: dict[str, object] = {
        "schema_version": 1,
        "release": release,
        "defaults": sorted(defaults, key=lambda value: _identity(value, "default")),
        "datasets": sorted(datasets, key=lambda value: _identity(value, "dataset")),
    }
    if errata:
        index["errata"] = list(errata)
    _validate_schema(index, "index-v1.schema.json", schema_directory, "generated index")

    index_bytes = _json_bytes(index)
    selector = {
        "schema_version": 1,
        "release": release,
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "index_url": (
            f"https://github.com/{release_record['repository']}/releases/download/"
            f"{release_record['tag']}/index.json"
        ),
    }
    _validate_schema(
        selector, "selector-v1.schema.json", schema_directory, "generated selector"
    )
    return index_bytes, _json_bytes(selector)


def build_catalog(*, root: Path | None = None) -> bytes:
    """Return the deterministic catalog for validated production releases."""

    source_root = (root or ROOT).resolve()
    schema_directory = source_root / "spec" / "schema"
    release_paths = sorted(
        (source_root / "registry" / "releases").glob("*/release.yaml")
    )
    if not release_paths:
        raise ValueError("registry catalog requires at least one release")

    selectors: list[Mapping[str, Any]] = []
    release_names: set[str] = set()
    for release_path in release_paths:
        index_bytes, selector_bytes = build(release_path, root=source_root)
        index_path = release_path.parent / "index.json"
        selector_path = release_path.parent / "selector.json"
        if not index_path.is_file() or index_path.read_bytes() != index_bytes:
            raise ValueError(f"release index is stale: {index_path}")
        if not selector_path.is_file() or selector_path.read_bytes() != selector_bytes:
            raise ValueError(f"release selector is stale: {selector_path}")
        selector = _load_json(selector_path)
        _validate_schema(
            selector,
            "selector-v1.schema.json",
            schema_directory,
            str(selector_path),
        )
        release = _string(selector.get("release"), "selector.release")
        if release in release_names:
            raise ValueError(f"duplicate catalog release {release!r}")
        release_names.add(release)
        selectors.append(selector)

    catalog = {
        "schema_version": 1,
        "releases": sorted(
            selectors, key=lambda selector: cast(str, selector["release"])
        ),
    }
    _validate_schema(
        catalog, "catalog-v1.schema.json", schema_directory, "generated catalog"
    )
    return _json_bytes(catalog)


def _write_or_check(path: Path, expected: bytes, check: bool) -> bool:
    if path.exists():
        if path.read_bytes() != expected:
            if check:
                print(f"generated file is stale: {path}", file=sys.stderr)
                return False
            raise ValueError(f"refusing to replace immutable release file: {path}")
        return True
    if check:
        print(f"generated file is missing: {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    return True


def _write_generated(path: Path, expected: bytes, check: bool) -> bool:
    if path.exists() and path.read_bytes() == expected:
        return True
    if check:
        print(f"generated file is stale: {path}", file=sys.stderr)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    return True


def main() -> int:
    """Build a release or check its schemas and immutable generated bytes."""

    parser = argparse.ArgumentParser(prog="dm-index")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "check"):
        subparser = commands.add_parser(command)
        subparser.add_argument("release", type=Path, nargs="?", default=DEFAULT_RELEASE)
        subparser.add_argument("--root", type=Path, default=ROOT)
    arguments = parser.parse_args()
    check = arguments.command == "check"

    try:
        source_root = arguments.root.resolve()
        release_path = arguments.release
        if not release_path.is_absolute():
            release_path = source_root / release_path
        release_path = release_path.resolve()
        index_bytes, selector_bytes = build(release_path, root=source_root)
        current = _write_or_check(
            release_path.parent / "index.json", index_bytes, check
        )
        current &= _write_or_check(
            release_path.parent / "selector.json", selector_bytes, check
        )
        if (
            current
            and release_path.parent.parent == source_root / "registry" / "releases"
        ):
            catalog_bytes = build_catalog(root=source_root)
            current &= _write_generated(
                source_root / "registry" / "catalog.json", catalog_bytes, check
            )
    except (OSError, ValueError) as error:
        print(f"dm-index: {error}", file=sys.stderr)
        return 2
    return 0 if current else 1


if __name__ == "__main__":
    raise SystemExit(main())
