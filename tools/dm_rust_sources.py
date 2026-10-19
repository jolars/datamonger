#!/usr/bin/env python3
"""Synchronize the Rust core bundled in the R source package and test fixtures."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "crates/datamonger-core"
BUNDLE = ROOT / "packages/r/src/rust/datamonger-core"


def license_notices(archive_path: Path) -> bytes:
    notices = [
        "Rust source authorship and licenses\n",
        "The R package includes datamonger-core and the following vendored crates.",
        "Crate metadata and complete bundled license notices follow.\n",
    ]
    packages = {
        "datamonger-core": (
            tomllib.loads((CORE / "Cargo.toml").read_text(encoding="utf-8")),
            {"LICENSE": (CORE / "LICENSE").read_bytes()},
        )
    }
    with tarfile.open(archive_path, "r:xz") as archive:
        members = {m.name: m for m in archive.getmembers() if m.isfile()}
        for name in sorted(members):
            path = PurePosixPath(name)
            if len(path.parts) != 3 or path.name != "Cargo.toml":
                continue
            stream = archive.extractfile(members[name])
            assert stream is not None
            metadata = tomllib.loads(stream.read().decode("utf-8"))
            licenses = {}
            for candidate, member in sorted(members.items()):
                license_path = PurePosixPath(candidate)
                if license_path.parent != path.parent or not any(
                    word in license_path.name.upper()
                    for word in ("LICENSE", "COPYING", "COPYRIGHT", "NOTICE")
                ):
                    continue
                stream = archive.extractfile(member)
                assert stream is not None
                licenses[license_path.name] = stream.read()
            packages[path.parent.name] = (metadata, licenses)
    for metadata, licenses in packages.values():
        package = metadata["package"]
        notices.extend(
            [
                "=" * 72,
                f"{package['name']} {package['version']}",
                "Authors: " + "; ".join(package.get("authors", [])),
                "License: " + package.get("license", "See bundled license files."),
            ]
        )
        for filename, contents in sorted(licenses.items()):
            notices.extend([f"\n--- {filename} ---\n", contents.decode("utf-8")])
    return ("\n".join(notices) + "\n").replace("\r\n", "\n").encode("utf-8")


def expected_sources() -> dict[Path, bytes]:
    files = [CORE / name for name in ("Cargo.toml", "README.md", "LICENSE")]
    files.extend(sorted((CORE / "src").rglob("*.rs")))
    return {path.relative_to(CORE): path.read_bytes() for path in files}


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
    mode.add_argument("--archive-vendor", action="store_true")
    args = parser.parse_args()
    bundled = synchronize_bytes(expected_sources(), BUNDLE, check=args.check)
    fixtures = synchronize(
        ROOT / "tests/conformance",
        CORE / "tests/fixtures/conformance",
        check=args.check,
    )
    rust = ROOT / "packages/r/src/rust"
    stamp = rust / "vendor-lock.sha256"
    lockfile = (rust / "Cargo.lock").read_text(encoding="utf-8").encode("utf-8")
    expected_stamp = hashlib.sha256(lockfile).hexdigest()
    if args.archive_vendor:
        if not (rust / "vendor").is_dir():
            parser.error("run rextendr::vendor_crates() before archiving")
        with tarfile.open(rust / "vendor.tar.xz", "w:xz", preset=6) as archive:
            for path in sorted((rust / "vendor").rglob("*")):
                if not path.is_file():
                    continue
                info = archive.gettarinfo(str(path), str(path.relative_to(rust)))
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
        stamp.write_text(expected_stamp + "\n")
    vendor = (
        (rust / "vendor.tar.xz").is_file()
        and stamp.is_file()
        and stamp.read_text().strip() == expected_stamp
    )
    if args.check and not vendor:
        print("Stale vendored dependencies: run dm-vendor-r")
    notices_match = True
    if (rust / "vendor.tar.xz").is_file():
        expected_notices = license_notices(rust / "vendor.tar.xz")
        notices = ROOT / "packages/r/inst/COPYRIGHTS"
        notices_match = notices.is_file() and notices.read_bytes() == expected_notices
        if args.check and not notices_match:
            print("Stale Rust license notices: run python tools/dm_rust_sources.py")
        elif not args.check:
            notices.write_bytes(expected_notices)
    valid = bundled and fixtures and notices_match and vendor
    return 0 if valid or not args.check else 1


if __name__ == "__main__":
    raise SystemExit(main())
