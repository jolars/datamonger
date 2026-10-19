from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/publish-core.yml").read_text())
VALIDATE = next(
    step["run"]
    for step in WORKFLOW["jobs"]["publish"]["steps"]
    if step.get("name") == "Match crate and tag versions"
)


@pytest.mark.parametrize(
    ("version", "tag", "success"),
    [
        ("0.1.0", "datamonger-core-v0.1.0", True),
        ("0.2.0-rc.1", "datamonger-core-v0.2.0-rc.1", True),
        ("0.1.0", "datamonger-core-v0.2.0", False),
        ("0.1.0", "datamonger-r-v0.1.0", False),
        ("0.1.0", "v0.1.0", False),
    ],
)
def test_publication_requires_matching_crate_and_tag(
    tmp_path: Path, version: str, tag: str, success: bool
) -> None:
    (tmp_path / "Cargo.toml").write_text(
        f'[package]\nname = "datamonger-core"\nversion = "{version}"\n'
    )
    env = {**os.environ, "RELEASE_TAG": tag}
    env.pop("LD_LIBRARY_PATH", None)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", VALIDATE],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == success, result.stderr
    if not success:
        assert "Expected release tag" in result.stderr
