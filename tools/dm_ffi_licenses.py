#!/usr/bin/env python3
"""Collect license notices for the native Julia artifact's Rust dependencies."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


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
    notices = ["Rust source authorship and licenses\n"]
    for package in sorted(metadata["packages"], key=lambda p: p["name"]):
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
