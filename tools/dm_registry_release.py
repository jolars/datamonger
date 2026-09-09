"""Prepare and check registry snapshots on Versionary release branches."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import dm_index
import yaml

ROOT = Path(__file__).resolve().parents[1]
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


def _target(root: Path) -> tuple[str, str]:
    version = (root / "registry/version.txt").read_text(encoding="utf-8").strip()
    if not _VERSION.fullmatch(version):
        raise ValueError("registry version must be a stable semantic version")
    targets: list[tuple[str, str]] = []
    for path in (root / ".versionary-manifest.json.d").glob("*.json"):
        state = json.loads(path.read_bytes())
        if state.get("path") != "registry":
            continue
        target = state.get("release-target", {})
        if (
            target.get("path") != "registry"
            or target.get("version") != version
            or not isinstance(target.get("tag"), str)
        ):
            raise ValueError("Versionary registry target does not match version.txt")
        targets.append((version, target["tag"]))
    if len(targets) != 1:
        raise ValueError("expected exactly one Versionary registry target")
    return targets[0]


def _outputs(root: Path, version: str) -> dict[Path, bytes]:
    collection = dict(dm_index.load_yaml(root / "registry/collection.yaml"))
    if set(collection) - {
        "schema_version",
        "repository",
        "manifests",
        "defaults",
        "errata",
    }:
        raise ValueError("registry collection contains unsupported fields")
    release_directory = Path("registry/releases") / version
    sequences = [
        dm_index.load_yaml(path)["sequence"]
        for path in (root / "registry/releases").glob("*/release.yaml")
        if path.parent.name != version
    ]
    if any(
        isinstance(value, bool) or not isinstance(value, int) for value in sequences
    ):
        raise ValueError("historical registry sequences must be integers")
    source = {
        **collection,
        "release": version,
        "sequence": max(sequences, default=-1) + 1,
        "tag": f"registry-v{version}",
    }
    source_bytes = yaml.safe_dump(source, sort_keys=False).encode("utf-8")

    # Validate the complete release before writing anything to the checkout.
    with tempfile.TemporaryDirectory(prefix="datamonger-release-") as directory:
        staging = Path(directory)
        for relative in ("registry", "spec/schema"):
            shutil.copytree(root / relative, staging / relative)
        release_path = staging / release_directory / "release.yaml"
        release_path.parent.mkdir(parents=True, exist_ok=True)
        release_path.write_bytes(source_bytes)
        index, selector = dm_index.build(release_path, root=staging)
        (release_path.parent / "index.json").write_bytes(index)
        (release_path.parent / "selector.json").write_bytes(selector)
        catalog = dm_index.build_catalog(root=staging)
    return {
        release_directory / "release.yaml": source_bytes,
        release_directory / "index.json": index,
        release_directory / "selector.json": selector,
        Path("registry/catalog.json"): catalog,
        Path("registry/latest.json"): selector,
    }


def prepare(root: Path, *, check_only: bool = False) -> None:
    """Generate one Versionary target without replacing immutable release files."""
    root = root.resolve()
    version, tag = _target(root)
    if tag != f"registry-v{version}":
        raise ValueError("prepare requires a new Versionary registry release target")
    outputs = _outputs(root, version)
    for relative, contents in outputs.items():
        path = root / relative
        if check_only:
            if not path.is_file() or path.read_bytes() != contents:
                raise ValueError(
                    f"generated registry file is missing or stale: {relative}"
                )
        elif (
            relative.is_relative_to("registry/releases")
            and path.exists()
            and path.read_bytes() != contents
        ):
            raise ValueError(f"refusing to replace immutable registry file: {relative}")
    if not check_only:
        for relative, contents in outputs.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)


def check(root: Path, *, pending: bool = False) -> None:
    """Verify the selected snapshot, catalog, and optional pending release inputs."""
    root = root.resolve()
    version, tag = _target(root)
    if (version, tag) == ("1.0.0", "registry-2026.09"):
        release = "2026.09"
    elif tag == f"registry-v{version}":
        release = version
    else:
        raise ValueError("unsupported Versionary registry target")
    directory = root / "registry/releases" / release
    source = dm_index.load_yaml(directory / "release.yaml")
    if source["release"] != release or source["tag"] != tag:
        raise ValueError("registry source does not match the Versionary target")
    index, selector = dm_index.build(directory / "release.yaml", root=root)
    for filename, contents in (("index.json", index), ("selector.json", selector)):
        if (directory / filename).read_bytes() != contents:
            raise ValueError(f"registry {filename} is stale")
    if (root / "registry/latest.json").read_bytes() != selector:
        raise ValueError(
            "registry latest selector does not match the Versionary target"
        )
    if (root / "registry/catalog.json").read_bytes() != dm_index.build_catalog(
        root=root
    ):
        raise ValueError("registry catalog is stale")
    if pending:
        prepare(root, check_only=True)


def main() -> int:
    """Run the registry release preparation or verification command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "check"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--pending", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.command == "prepare":
            prepare(arguments.root)
        else:
            check(arguments.root, pending=arguments.pending)
    except (OSError, ValueError) as error:
        print(f"dm-registry-release: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
