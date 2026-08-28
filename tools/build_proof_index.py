"""Build the provisional vertical-proof registry index."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "registry" / "releases" / "proof-0001" / "release.yaml"


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


def _identifier(record: Mapping[str, Any], field: str) -> tuple[str, str, str]:
    return (
        _string(record.get("source"), f"{field}.source"),
        _string(record.get("name"), f"{field}.name"),
        _string(record.get("version"), f"{field}.version"),
    )


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

    defaults = [
        _mapping(value, "default")
        for value in _sequence(release_record.get("defaults"), "defaults")
    ]
    default_identifiers = [_identifier(default, "default") for default in defaults]
    if len(default_identifiers) != len(set(default_identifiers)):
        raise ValueError("default identifiers must be unique")
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
