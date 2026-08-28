"""Build the provisional vertical-proof registry index."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "registry" / "releases" / "proof-0001" / "release.yaml"

# These grammars are normative in DESIGN.md and enforced by every client at
# fetch time, so a value that violates them must never publish: releases are
# immutable, and a malformed entry would be unfetchable by construction.
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be an array")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _load_yaml(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        return _mapping(yaml.safe_load(source), str(path))


def _grammar(value: str, pattern: re.Pattern[str], field: str) -> str:
    if pattern.fullmatch(value) is None:
        raise ValueError(f"{field} {value!r} violates its normative grammar")
    return value


def _digest(value: object, field: str) -> str:
    digest = _string(value, field)
    if _SHA256.fullmatch(digest) is None:
        raise ValueError(f"{field} {digest!r} must be lowercase SHA-256 hex")
    return digest


def _identifier(record: Mapping[str, Any], field: str) -> tuple[str, str, str]:
    return (
        _grammar(
            _string(record.get("source"), f"{field}.source"),
            _IDENTIFIER,
            f"{field}.source",
        ),
        _grammar(
            _string(record.get("name"), f"{field}.name"),
            _IDENTIFIER,
            f"{field}.name",
        ),
        _grammar(
            _string(record.get("version"), f"{field}.version"),
            _VERSION,
            f"{field}.version",
        ),
    )


def _validate_dataset(dataset: Mapping[str, Any]) -> None:
    if dataset.get("schema_version") != 1:
        raise ValueError(
            f"unsupported manifest schema {dataset.get('schema_version')!r}"
        )
    for raw_artifact in _sequence(dataset.get("artifacts"), "artifacts"):
        artifact = _mapping(raw_artifact, "artifact")
        _digest(artifact.get("sha256"), "artifact.sha256")
    representation = _mapping(dataset.get("representation"), "representation")
    expect = _mapping(representation.get("expect"), "representation.expect")
    for raw_record in _sequence(expect.get("verification"), "expect.verification"):
        record = _mapping(raw_record, "verification record")
        _digest(record.get("digest"), "verification.digest")


def _json_bytes(value: object) -> bytes:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded.encode("utf-8") + b"\n"


def build(release_path: Path) -> tuple[bytes, bytes]:
    """Return the generated index and strong-selector documents."""

    release_record = _load_yaml(release_path)
    release = _string(release_record.get("release"), "release")
    repository = _string(release_record.get("repository"), "repository")
    tag = _string(release_record.get("tag"), "tag")

    datasets = [
        _load_yaml(ROOT / _string(path, "manifest path"))
        for path in _sequence(release_record.get("manifests"), "manifests")
    ]
    identifiers = [_identifier(dataset, "dataset") for dataset in datasets]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("dataset identifiers must be unique")
    for dataset in datasets:
        _validate_dataset(dataset)

    defaults = [
        _mapping(value, "default")
        for value in _sequence(release_record.get("defaults"), "defaults")
    ]
    default_identifiers = [_identifier(default, "default") for default in defaults]
    # Clients resolve a default by (source, name) alone, so uniqueness on the
    # full triple would let two versions of one dataset both claim the default.
    default_keys = [(source, name) for source, name, _ in default_identifiers]
    if len(default_keys) != len(set(default_keys)):
        raise ValueError("each dataset may declare at most one default version")
    unknown_defaults = set(default_identifiers) - set(identifiers)
    if unknown_defaults:
        raise ValueError(f"defaults refer to unknown datasets: {unknown_defaults}")

    index = {
        "schema_version": 1,
        "release": release,
        "defaults": sorted(defaults, key=lambda value: _identifier(value, "default")),
        "datasets": sorted(datasets, key=lambda value: _identifier(value, "dataset")),
    }
    index_bytes = _json_bytes(index)
    selector = {
        "release": release,
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "index_url": (
            f"https://github.com/{repository}/releases/download/{tag}/index.json"
        ),
    }
    return index_bytes, _json_bytes(selector)


def _write_or_check(path: Path, expected: bytes, check: bool) -> bool:
    if check:
        if not path.exists() or path.read_bytes() != expected:
            print(f"generated file is stale: {path}")
            return False
        return True
    path.write_bytes(expected)
    return True


def main() -> int:
    """Generate the configured proof release or verify checked-in output."""

    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path, nargs="?", default=DEFAULT_RELEASE)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    release_path = arguments.release.resolve()
    index_bytes, selector_bytes = build(release_path)
    output_directory = release_path.parent
    current = _write_or_check(
        output_directory / "index.json", index_bytes, arguments.check
    )
    current &= _write_or_check(
        output_directory / "selector.json", selector_bytes, arguments.check
    )
    return 0 if current else 1


if __name__ == "__main__":
    raise SystemExit(main())
