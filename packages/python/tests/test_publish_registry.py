from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/publish-registry.yml").read_text())
ATTACH = next(
    step["run"]
    for step in WORKFLOW["jobs"]["publish"]["steps"]
    if step.get("name") == "Attach and verify the immutable index"
)


@pytest.fixture
def publisher(tmp_path: Path) -> tuple[dict[str, str], Path]:
    binary = tmp_path / "gh"
    binary.write_text(
        f"#!{sys.executable}\n"
        """import json
import os
import sys
from pathlib import Path

path = Path(os.environ['FAKE_RELEASE'])
state = json.loads(path.read_text())
args = sys.argv[1:]
state['calls'].append(args)
if args[:2] == ['release', 'view']:
    print(json.dumps(state['assets']))
elif args[:2] == ['release', 'upload']:
    assert '--clobber' not in args
    state['assets'] = [{'name': 'index.json'}]
    state['body'] = Path(args[3]).read_text()
elif args[:2] == ['release', 'download']:
    directory = Path(args[args.index('--dir') + 1])
    (directory / 'index.json').write_text(state['body'])
else:
    raise AssertionError(args)
path.write_text(json.dumps(state))
"""
    )
    binary.chmod(0o755)
    state = tmp_path / "release.json"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        "FAKE_RELEASE": str(state),
        "RELEASE_TAG": "registry-v1.1.0",
        "RELEASE_DIRECTORY": str(ROOT / "registry/releases/2026.09"),
        "RUNNER_TEMP": str(tmp_path),
    }
    return env, state


@pytest.mark.parametrize(
    ("draft", "assets", "corrupt", "success", "uploaded"),
    [
        (True, [], False, True, True),
        (True, [{"name": "index.json"}], False, True, False),
        (False, [{"name": "index.json"}], False, True, False),
        (False, [], False, False, False),
        (True, [{"name": "unexpected.json"}], False, False, False),
        (True, [{"name": "index.json"}, {"name": "data.csv"}], False, False, False),
        (True, [{"name": "index.json"}], True, False, False),
        (False, [{"name": "index.json"}], True, False, False),
    ],
)
def test_index_publication_is_immutable_and_retryable(
    publisher: tuple[dict[str, str], Path],
    draft: bool,
    assets: list[dict[str, str]],
    corrupt: bool,
    success: bool,
    uploaded: bool,
) -> None:
    env, state = publisher
    body = (
        "corrupt"
        if corrupt
        else (ROOT / "registry/releases/2026.09/index.json").read_text()
    )
    state.write_text(json.dumps({"calls": [], "assets": assets, "body": body}))
    env["RELEASE_DRAFT"] = str(draft).lower()
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", ATTACH],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) == success, result.stderr
    calls = json.loads(state.read_text())["calls"]
    assert any(call[:2] == ["release", "upload"] for call in calls) == uploaded
