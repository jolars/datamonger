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


def detect_outputs(directory: Path, event: str, base: str, head: str) -> dict[str, str]:
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
    decisions = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert set(decisions) == {"required", "r_vendor_changed"}
    assert set(decisions.values()) <= {"true", "false"}
    return decisions


def detect(directory: Path, event: str, base: str, head: str) -> bool:
    return detect_outputs(directory, event, base, head)["required"] == "true"


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
    decisions = detect_outputs(repository, "push", base, head)
    assert decisions == {"required": "true", "r_vendor_changed": "true"}


@pytest.mark.parametrize(
    ("path", "changed"),
    [
        ("packages/r/src/rust/vendor.tar.xz", "true"),
        ("packages/r/src/rust/Cargo.lock", "true"),
        ("packages/r/src/rust/Cargo.toml", "true"),
        ("packages/r/src/rust/src/lib.rs", "true"),
        ("packages/r/DESCRIPTION", "false"),
        ("packages/python/rust/lib.rs", "false"),
    ],
)
def test_selects_r_build_for_rust_adapter_changes(
    repository: Path, path: str, changed: str
) -> None:
    base = git(repository, "rev-parse", "HEAD")
    head = commit(repository, path)
    decisions = detect_outputs(repository, "pull_request", base, head)
    assert decisions["r_vendor_changed"] == changed


@pytest.mark.parametrize("operation", ["delete", "move"])
def test_removing_rust_adapter_files_still_runs_r(
    repository: Path, operation: str
) -> None:
    base = commit(repository, "packages/r/src/rust/vendor.tar.xz")
    if operation == "delete":
        git(repository, "rm", "packages/r/src/rust/vendor.tar.xz")
    else:
        git(repository, "mv", "packages/r/src/rust/vendor.tar.xz", "vendor.tar.xz")
    git(repository, "commit", "-m", "remove vendor archive")
    head = git(repository, "rev-parse", "HEAD")
    decisions = detect_outputs(repository, "pull_request", base, head)
    assert decisions["r_vendor_changed"] == "true"


def test_r_build_ignores_vendor_changes_only_on_base_branch(repository: Path) -> None:
    git(repository, "checkout", "-b", "release")
    head = commit(repository, "packages/r/DESCRIPTION")
    git(repository, "checkout", "main")
    base = commit(repository, "packages/r/src/rust/vendor.tar.xz")
    decisions = detect_outputs(repository, "pull_request", base, head)
    assert decisions["r_vendor_changed"] == "false"


@pytest.mark.parametrize(
    ("changes", "required", "distributions", "policy", "run_checks", "success"),
    [
        ("success", "true", "success", "success", "true", True),
        ("success", "false", "skipped", "success", "true", True),
        ("success", "true", "failure", "success", "true", False),
        ("success", "true", "cancelled", "success", "true", False),
        ("success", "true", "skipped", "success", "true", False),
        ("success", "false", "failure", "success", "true", False),
        ("success", "false", "success", "success", "true", False),
        ("success", "", "skipped", "success", "true", False),
        ("failure", "false", "skipped", "success", "true", False),
        ("cancelled", "false", "skipped", "success", "true", False),
        ("skipped", "false", "skipped", "success", "true", False),
        ("success", "true", "skipped", "success", "false", True),
        ("success", "false", "skipped", "success", "false", True),
        ("success", "true", "failure", "success", "false", False),
        ("success", "true", "cancelled", "success", "false", False),
        ("failure", "true", "skipped", "success", "false", False),
        ("success", "true", "success", "failure", "", False),
        ("success", "true", "skipped", "failure", "", False),
    ],
)
def test_status_accepts_only_successful_builds_or_deliberate_skips(
    changes: str,
    required: str,
    distributions: str,
    policy: str,
    run_checks: str,
    success: bool,
) -> None:
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", STATUS],
        env=environment(
            CHANGES_RESULT=changes,
            DISTRIBUTIONS_REQUIRED=required,
            DISTRIBUTIONS_RESULT=distributions,
            POLICY_RESULT=policy,
            RUN_CHECKS=run_checks,
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is success, result.stderr
