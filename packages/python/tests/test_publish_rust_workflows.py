from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("crate", "workflow_name"),
    [("datamonger-core", "publish-core.yml"), ("datamonger", "publish-cli.yml")],
)
@pytest.mark.parametrize(
    ("version", "tag", "success"),
    [
        ("0.1.0", "{crate}-v0.1.0", True),
        ("0.2.0-rc.1", "{crate}-v0.2.0-rc.1", True),
        ("0.1.0", "{crate}-v0.2.0", False),
        ("0.1.0", "datamonger-r-v0.1.0", False),
        ("0.1.0", "datamonger-cli-v0.1.0", False),
        ("0.1.0", "v0.1.0", False),
    ],
)
def test_publication_requires_matching_crate_and_tag(
    tmp_path: Path,
    crate: str,
    workflow_name: str,
    version: str,
    tag: str,
    success: bool,
) -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows" / workflow_name).read_text())
    validate = next(
        step["run"]
        for step in workflow["jobs"]["publish"]["steps"]
        if step.get("name") == "Match crate and tag versions"
    )
    (tmp_path / "Cargo.toml").write_text(
        f'[package]\nname = "{crate}"\nversion = "{version}"\n'
    )
    env = {**os.environ, "RELEASE_TAG": tag.format(crate=crate)}
    env.pop("LD_LIBRARY_PATH", None)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", validate],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == success, result.stderr
    if not success:
        assert "Expected release tag" in result.stderr
