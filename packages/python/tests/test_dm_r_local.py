from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[3] / "tools"
SPEC = importlib.util.spec_from_file_location("dm_r_local", TOOLS / "dm_r_local.py")
assert SPEC is not None and SPEC.loader is not None
dm_r_local = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_r_local)


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_local_core_version_and_release_files_are_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: bool, newline: bytes
) -> None:
    rust = tmp_path / "packages/r/src/rust"
    rust.mkdir(parents=True)
    core = tmp_path / "crates/datamonger-core"
    core.mkdir(parents=True)
    (core / "Cargo.toml").write_text('[package]\nversion = "0.2.0"\n')
    original = (
        b'datamonger_core = { package = "datamonger-core", version = "0.1" }' + newline
    )
    (rust / "Cargo.toml").write_bytes(original)
    (rust / "Cargo.lock").write_bytes(b"release lock\n")
    monkeypatch.setattr(dm_r_local, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["dm_r_local.py", "-e", "test()"])

    # Emulate Windows text output translation even when this test runs on Unix.
    write_text = Path.write_text

    def windows_write_text(path: Path, text: str, **kwargs: object) -> int:
        if path == rust / "Cargo.toml":
            path.write_bytes(text.replace("\n", "\r\n").encode())
            return len(text)
        return write_text(path, text, **kwargs)

    monkeypatch.setattr(Path, "write_text", windows_write_text)

    def run(command: list[str], *, env: dict[str, str]) -> int:
        assert command == ["Rscript", "-e", "test()"]
        assert env["DM_R_CORE_PATH"] == str(core)
        assert (rust / "Cargo.toml").read_bytes().endswith(newline)
        assert b"\r\r\n" not in (rust / "Cargo.toml").read_bytes()
        dependency = tomllib.loads((rust / "Cargo.toml").read_text())
        assert dependency["datamonger_core"]["version"] == "=0.2.0"
        (rust / "Cargo.lock").write_bytes(b"local lock\n")
        if fails:
            raise OSError("Rscript failed")
        return 7

    monkeypatch.setattr(dm_r_local.subprocess, "call", run)
    if fails:
        with pytest.raises(OSError, match="Rscript failed"):
            dm_r_local.main()
    else:
        assert dm_r_local.main() == 7
    assert (rust / "Cargo.toml").read_bytes() == original
    assert (rust / "Cargo.lock").read_bytes() == b"release lock\n"
