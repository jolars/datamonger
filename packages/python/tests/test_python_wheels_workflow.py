from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
DETECT = next(
    step["run"]
    for step in WORKFLOW["jobs"]["python-distribution-changes"]["steps"]
    if step.get("name") == "Check changed paths"
)
STATUS = WORKFLOW["jobs"]["python-distributions-status"]["steps"][0]["run"]


def environment(**values: str) -> dict[str, str]:
    env = {**os.environ, **values}
    # Devenv's Python libraries are incompatible with the external Nix Git binary.
    env.pop("LD_LIBRARY_PATH", None)
    return env


def git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *args],
        env=environment(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(directory: Path, path: str, contents: str = "changed\n") -> str:
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents)
    git(directory, "add", "--", path)
    git(directory, "commit", "-m", "change")
    return git(directory, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    directory = tmp_path / "repository"
    directory.mkdir()
    git(directory, "init", "--initial-branch=main")
    for key, value in {
        "user.name": "Test",
        "user.email": "test@example.com",
        "commit.gpgsign": "false",
        "core.hooksPath": os.devnull,
        "core.excludesFile": os.devnull,
    }.items():
        git(directory, "config", key, value)
    commit(directory, "README.md", "baseline\n")
    commit(directory, "packages/python/rust/lib.rs", "baseline\n")
    return directory


def detect(directory: Path, event: str, base: str, head: str) -> bool:
    output = directory.parent / "github-output"
    output.unlink(missing_ok=True)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", DETECT],
        cwd=directory,
        env=environment(
            GITHUB_EVENT_NAME=event,
            BASE_SHA=base,
            HEAD_SHA=head,
            RUNNER_TEMP=str(directory.parent),
            GITHUB_OUTPUT=str(output),
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    decision = output.read_text().strip()
    assert decision in {"required=true", "required=false"}
    return decision == "required=true"


@pytest.mark.parametrize(
    ("path", "required"),
    [
        ("packages/python/rust/lib.rs", True),
        ("packages/python/src/datamonger/_data/index.json", True),
        ("packages/python/pyproject.toml", True),
        ("packages/python/Cargo.lock", True),
        ("packages/python/uv.lock", True),
        ("crates/datamonger-core/src/lib.rs", True),
        ("tests/conformance/cases.json", True),
        (".cargo/config.toml", True),
        (".github/actions/build/action.yml", True),
        (".github/workflows/python-wheels.yml", True),
        (".github/workflows/publish-python.yml", True),
        (".github/workflows/ci.yml", True),
        ("rust-toolchain.toml", True),
        (".gitattributes", True),
        ("Cargo.lock", True),
        ("README.md", False),
        ("documentation/pages/index.md", False),
        ("packages/r/R/registry.R", False),
        ("packages/julia/src/lib.jl", False),
        ("crates/datamonger-ffi/src/lib.rs", False),
        ("packages/cli/src/main.rs", False),
        ("curation/example/1/README.md", False),
        ("registry/datasets/source/example.yaml", False),
        ("tools/dm_r_local.py", False),
        ("packages/python-other/example.py", False),
    ],
)
def test_push_selects_only_distribution_inputs(
    repository: Path, path: str, required: bool
) -> None:
    base = git(repository, "rev-parse", "HEAD")
    head = commit(repository, path)
    assert detect(repository, "push", base, head) is required


def test_push_checks_every_commit_in_the_push(repository: Path) -> None:
    base = git(repository, "rev-parse", "HEAD")
    native = commit(repository, "packages/python/rust/lib.rs")
    head = commit(repository, "docs/note.md")
    assert detect(repository, "push", base, head)
    assert not detect(repository, "push", native, head)


@pytest.mark.parametrize("operation", ["delete", "move"])
def test_removing_distribution_inputs_still_runs_wheels(
    repository: Path, operation: str
) -> None:
    base = git(repository, "rev-parse", "HEAD")
    if operation == "delete":
        git(repository, "rm", "packages/python/rust/lib.rs")
    else:
        git(repository, "mv", "packages/python/rust/lib.rs", "example.rs")
    git(repository, "commit", "-m", "remove binding")
    assert detect(repository, "push", base, git(repository, "rev-parse", "HEAD"))


@pytest.mark.parametrize(
    ("path", "required"),
    [("packages/r/R/api.R", False), ("packages/python/rust/lib.rs", True)],
)
def test_pull_request_ignores_changes_only_on_the_base_branch(
    repository: Path, path: str, required: bool
) -> None:
    git(repository, "checkout", "-b", "feature")
    head = commit(repository, path)
    git(repository, "checkout", "main")
    base = commit(repository, "packages/python/pyproject.toml")
    assert detect(repository, "pull_request", base, head) is required


def test_pull_request_checks_the_whole_branch(repository: Path) -> None:
    base = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-b", "feature")
    commit(repository, "packages/python/rust/lib.rs")
    head = commit(repository, "docs/note.md")
    assert detect(repository, "pull_request", base, head)


def test_force_push_checks_the_previous_tree(repository: Path) -> None:
    baseline = git(repository, "rev-parse", "HEAD")
    before = commit(repository, "packages/python/rust/lib.rs")
    git(repository, "checkout", "-b", "rewritten", baseline)
    head = commit(repository, "packages/r/R/api.R")
    assert detect(repository, "push", before, head)


@pytest.mark.parametrize("base", ["", "0" * 40, "f" * 40])
def test_unknown_history_runs_the_full_matrix(repository: Path, base: str) -> None:
    head = commit(repository, "docs/note.md")
    assert detect(repository, "push", base, head)


@pytest.mark.parametrize(
    ("changes", "required", "distributions", "success"),
    [
        ("success", "true", "success", True),
        ("success", "false", "skipped", True),
        ("success", "true", "failure", False),
        ("success", "true", "cancelled", False),
        ("success", "true", "skipped", False),
        ("success", "false", "failure", False),
        ("success", "false", "success", False),
        ("success", "", "skipped", False),
        ("failure", "false", "skipped", False),
        ("cancelled", "false", "skipped", False),
        ("skipped", "false", "skipped", False),
    ],
)
def test_status_accepts_only_successful_builds_or_deliberate_skips(
    changes: str, required: str, distributions: str, success: bool
) -> None:
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", STATUS],
        env=environment(
            CHANGES_RESULT=changes,
            DISTRIBUTIONS_REQUIRED=required,
            DISTRIBUTIONS_RESULT=distributions,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is success, result.stderr
