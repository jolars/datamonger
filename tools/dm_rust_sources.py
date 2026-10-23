#!/usr/bin/env python3
"""Check vendored Rust metadata and synchronize core test fixtures."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "crates/datamonger-core"


def synchronize(source: Path, destination: Path, *, check: bool) -> bool:
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    return synchronize_bytes(expected, destination, check=check)


def synchronize_bytes(
    expected: dict[Path, bytes], destination: Path, *, check: bool
) -> bool:
    actual = {
        path.relative_to(destination): path.read_bytes()
        for path in destination.rglob("*")
        if path.is_file()
    }
    if actual == expected:
        return True
    if check:
        print(f"Stale generated Rust sources: {destination.relative_to(ROOT)}")
        return False
    if destination.exists():
        shutil.rmtree(destination)
    for relative, contents in expected.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--record-vendor", action="store_true")
    args = parser.parse_args()
    fixtures = synchronize(
        ROOT / "tests/conformance",
        CORE / "tests/fixtures/conformance",
        check=args.check,
    )
    rust = ROOT / "packages/r/src/rust"
    stamp = rust / "vendor-lock.sha256"
    lockfile = (rust / "Cargo.lock").read_text(encoding="utf-8").encode("utf-8")
    expected_stamp = hashlib.sha256(lockfile).hexdigest()
    registry_core = any(
        package["name"] == "datamonger-core"
        and package.get("source", "").startswith("registry+")
        for package in tomllib.loads(lockfile.decode("utf-8"))["package"]
    )
    if args.record_vendor:
        if not registry_core or not (rust / "vendor.tar.xz").is_file():
            parser.error("vendor the published datamonger-core with dm-vendor-r first")
        stamp.write_text(expected_stamp + "\n")
    vendor = (
        (rust / "vendor.tar.xz").is_file()
        and stamp.is_file()
        and stamp.read_text().strip() == expected_stamp
        and registry_core
    )
    if args.check and not vendor:
        print("Stale vendored Rust sources: run dm-vendor-r")
    valid = fixtures and vendor
    return 0 if valid or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
