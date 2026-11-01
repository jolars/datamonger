from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parents[3] / "tools"
SPEC = importlib.util.spec_from_file_location(
    "dm_ffi_licenses", TOOLS / "dm_ffi_licenses.py"
)
assert SPEC is not None and SPEC.loader is not None
dm_ffi_licenses = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_ffi_licenses)


def test_native_notices_exclude_other_clients_and_test_dependencies() -> None:
    def dependency(package: str, *kinds: str | None) -> dict[str, Any]:
        return {"pkg": package, "dep_kinds": [{"kind": kind} for kind in kinds]}

    metadata = {
        "packages": [
            {"id": name, "name": name}
            for name in (
                "datamonger-ffi",
                "core",
                "compression",
                "build",
                "test",
                "cli",
            )
        ],
        "resolve": {
            "nodes": [
                {"id": "datamonger-ffi", "deps": [dependency("core", None)]},
                {
                    "id": "core",
                    "deps": [
                        dependency("compression", None, "dev"),
                        dependency("build", "build"),
                        dependency("test", "dev"),
                    ],
                },
                {"id": "compression", "deps": []},
                {"id": "build", "deps": []},
                {"id": "test", "deps": []},
                {"id": "cli", "deps": [dependency("core", None)]},
            ]
        },
    }
    assert dm_ffi_licenses.runtime_packages(metadata) == {
        "datamonger-ffi",
        "core",
        "compression",
        "build",
    }
