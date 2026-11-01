#!/usr/bin/env python3
"""Collect license notices for the native Julia artifact's Rust dependencies."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def runtime_packages(metadata: dict[str, Any]) -> set[str]:
    """Select the FFI dependency graph without unrelated workspace or test crates."""
    root = next(
        package["id"]
        for package in metadata["packages"]
        if package["name"] == "datamonger-ffi"
    )
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    selected: set[str] = set()
    pending = [root]
    while pending:
        package_id = pending.pop()
        if package_id in selected:
            continue
        selected.add(package_id)
        pending.extend(
            dependency["pkg"]
            for dependency in nodes[package_id]["deps"]
            if any(kind["kind"] != "dev" for kind in dependency["dep_kinds"])
        )
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metadata = json.loads(
        subprocess.check_output(
            [
                "cargo",
                "metadata",
                "--locked",
                "--format-version=1",
                "--manifest-path",
                str(ROOT / "crates/datamonger-ffi/Cargo.toml"),
            ],
            text=True,
        )
    )
    selected = runtime_packages(metadata)
    notices = ["Rust source authorship and licenses\n"]
    for package in sorted(metadata["packages"], key=lambda p: p["name"]):
        if package["id"] not in selected:
            continue
        notices.extend(
            [
                "=" * 72,
                f"{package['name']} {package['version']}",
                "Authors: " + "; ".join(package.get("authors", [])),
                "License: " + (package.get("license") or "See bundled license files."),
            ]
        )
        directory = Path(package["manifest_path"]).parent
        for path in sorted(directory.iterdir()):
            if path.is_file() and any(
                word in path.name.upper()
                for word in ("LICENSE", "COPYING", "COPYRIGHT", "NOTICE")
            ):
                notices.extend([f"\n--- {path.name} ---\n", path.read_text()])
    args.output.write_text("\n".join(notices) + "\n")


if __name__ == "__main__":
    main()
