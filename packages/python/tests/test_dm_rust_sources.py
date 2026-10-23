from __future__ import annotations

import importlib.util
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "dm_rust_sources", ROOT / "tools/dm_rust_sources.py"
)
assert SPEC is not None and SPEC.loader is not None
dm_rust_sources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_rust_sources)


@pytest.fixture
def source_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    files = {
        "crates/datamonger-core/src/lib.rs": b"pub fn decode() {}\n",
        "tests/conformance/fixture.csv": b"1,2\n",
        "packages/r/src/rust/Cargo.lock": (
            b'version = 3\n[[package]]\nname = "datamonger-core"\n'
            b'version = "0.1.0"\n'
            b'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
        ),
        "packages/r/src/rust/vendor/datamonger-core/Cargo.toml": (
            b'[package]\nname = "datamonger-core"\nversion = "0.1.0"\nlicense = "MIT"\n'
        ),
        "packages/r/src/rust/vendor/datamonger-core/LICENSE": b"Core license.\r\n",
    }
    for name, contents in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    rust = tmp_path / "packages/r/src/rust"
    with tarfile.open(rust / "vendor.tar.xz", "w:xz") as archive:
        archive.add(rust / "vendor", arcname="vendor")
    monkeypatch.setattr(dm_rust_sources, "ROOT", tmp_path)
    monkeypatch.setattr(dm_rust_sources, "CORE", tmp_path / "crates/datamonger-core")
    return tmp_path


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["dm_rust_sources", *args])
    return int(dm_rust_sources.main())


def test_records_metadata_without_repacking_vendor_archive(
    source_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = source_root / "packages/r/src/rust/vendor.tar.xz"
    contents = archive.read_bytes()
    assert run(monkeypatch, "--record-vendor") == 0
    assert archive.read_bytes() == contents
    assert not (source_root / "packages/r/inst/COPYRIGHTS").exists()
    assert run(monkeypatch, "--check") == 0
    (source_root / "crates/datamonger-core/src/lib.rs").write_bytes(
        b"unreleased edit\n"
    )
    assert run(monkeypatch, "--check") == 0


def test_check_rejects_stale_lock_without_rewriting_archive(
    source_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(monkeypatch, "--record-vendor") == 0
    archive = source_root / "packages/r/src/rust/vendor.tar.xz"
    contents = archive.read_bytes()
    lockfile = source_root / "packages/r/src/rust/Cargo.lock"
    lockfile.write_bytes(lockfile.read_bytes() + b"\n")
    assert run(monkeypatch, "--check") == 1
    assert archive.read_bytes() == contents


def test_rejects_local_core_in_release_lockfile(
    source_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(monkeypatch, "--record-vendor") == 0
    lockfile = source_root / "packages/r/src/rust/Cargo.lock"
    lockfile.write_text(
        "\n".join(
            line
            for line in lockfile.read_text().splitlines()
            if not line.startswith("source")
        )
    )
    assert run(monkeypatch, "--check") == 1
    with pytest.raises(SystemExit, match="2"):
        run(monkeypatch, "--record-vendor")
