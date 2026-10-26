"""Run Rscript with the local core, preserving the published dependency pin."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    rust = ROOT / "packages/r/src/rust"
    manifest = rust / "Cargo.toml"
    lock = rust / "Cargo.lock"
    original = manifest.read_bytes()
    original_lock = lock.read_bytes()
    core = ROOT / "crates/datamonger-core"
    version = tomllib.loads((core / "Cargo.toml").read_text())["package"]["version"]
    # Cargo ignores a path patch whose version does not satisfy the release pin.
    patched, count = re.subn(
        r'(datamonger_core\s*=\s*\{[^\n]*\bversion\s*=\s*)"[^"]+"',
        lambda match: f'{match[1]}"={version}"',
        original.decode(),
    )
    if count != 1:
        raise ValueError("expected one R core dependency pin")
    try:
        manifest.write_bytes(patched.encode())
        return subprocess.call(
            ["Rscript", *sys.argv[1:]],
            env={**os.environ, "DM_R_CORE_PATH": str(core), "DEBUG": "1"},
        )
    finally:
        manifest.write_bytes(original)
        lock.write_bytes(original_lock)


if __name__ == "__main__":
    raise SystemExit(main())
