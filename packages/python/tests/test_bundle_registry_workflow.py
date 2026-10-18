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
PROPOSE = next(
    step["run"]
    for step in WORKFLOW["jobs"]["bundle"]["steps"]
    if step.get("name") == "Open or update the client bundle PR"
)


def git(directory: Path, *args: str) -> str:
    env = dict(os.environ)
    # Devenv's Python libraries are incompatible with the external Nix Git binary.
    env.pop("LD_LIBRARY_PATH", None)
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def automation(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "--initial-branch=main", str(origin))
    source = tmp_path / "source"
    git(tmp_path, "clone", str(origin), str(source))
    (source / "README.md").write_text("Test repository\n")
    (source / "registry").mkdir()
    (source / "registry/latest.json").write_text('{"release":"1.2.0"}')
    bundle = source / "packages/cli/assets"
    bundle.mkdir(parents=True)
    (bundle / "index.json").write_text("1.1.0")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "baseline",
    )
    git(source, "push", "origin", "main")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"calls": [], "number": None}))
    for binary, code in {
        "uv": """import sys
from pathlib import Path
if '--check' not in sys.argv:
    Path('packages/cli/assets/index.json').write_text(sys.argv[-1])
""",
        "gh": """import json
import os
import sys
from pathlib import Path
state_path = Path(os.environ['FAKE_PR_STATE'])
state = json.loads(state_path.read_text())
args = sys.argv[1:]
state['calls'].append(args)
if args[:2] == ['pr', 'list']:
    print(state['number'] or '')
elif args[:2] in (['pr', 'create'], ['pr', 'edit']):
    if args[1] == 'create':
        assert state['number'] is None
        state['number'] = 42
    state['body'] = Path(args[args.index('--body-file') + 1]).read_text()
else:
    raise AssertionError(args)
state_path.write_text(json.dumps(state))
""",
    }.items():
        path = binaries / binary
        path.write_text(f"#!{sys.executable}\n" + code)
        path.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{binaries}{os.pathsep}{os.environ['PATH']}",
        "FAKE_PR_STATE": str(state),
        "RUNNER_TEMP": str(tmp_path),
        "DEFAULT_BRANCH": "main",
        "RELEASE_TAG": "registry-v1.2.0",
    }
    env.pop("LD_LIBRARY_PATH", None)
    return origin, env, state


def run_workflow(
    origin: Path, env: dict[str, str], directory: Path
) -> subprocess.CompletedProcess[str]:
    git(directory.parent, "clone", str(origin), str(directory))
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", PROPOSE],
        cwd=directory,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_retry_updates_one_pr_and_mentions_maintainer(
    automation: tuple[Path, dict[str, str], Path], tmp_path: Path
) -> None:
    origin, env, state_path = automation
    for attempt in range(2):
        result = run_workflow(origin, env, tmp_path / f"attempt-{attempt}")
        assert result.returncode == 0, result.stderr
    state = json.loads(state_path.read_text())
    assert sum(call[:2] == ["pr", "create"] for call in state["calls"]) == 1
    assert sum(call[:2] == ["pr", "edit"] for call in state["calls"]) == 1
    assert "@jolars" in state["body"]
    assert (
        git(origin, "show", "automation/bundle-registry:packages/cli/assets/index.json")
        == "1.2.0"
    )
    assert git(origin, "show", "main:packages/cli/assets/index.json") == "1.1.0"


@pytest.mark.parametrize("scenario", ["older", "already-bundled"])
def test_skips_obsolete_or_already_bundled_updates(
    automation: tuple[Path, dict[str, str], Path], tmp_path: Path, scenario: str
) -> None:
    origin, env, state_path = automation
    if scenario == "older":
        env["RELEASE_TAG"] = "registry-v1.1.0"
    else:
        source = tmp_path / "source"
        (source / "packages/cli/assets/index.json").write_text("1.2.0")
        git(source, "add", ".")
        git(
            source,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "bundle",
        )
        git(source, "push", "origin", "main")
    result = run_workflow(origin, env, tmp_path / "attempt")
    assert result.returncode == 0, result.stderr
    assert json.loads(state_path.read_text())["calls"] == []
    assert git(origin, "branch", "--list", "automation/bundle-registry") == ""
