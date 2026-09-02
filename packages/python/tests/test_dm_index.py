from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools" / "dm_index.py"
SPEC = importlib.util.spec_from_file_location("dm_index", TOOL)
assert SPEC is not None and SPEC.loader is not None
dm_index = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dm_index)


def manifest_template() -> dict[str, Any]:
    return yaml.safe_load(
        (ROOT / "registry/datasets/uci/iris-1.yaml").read_text(encoding="utf-8")
    )


def make_manifest(
    *,
    source: str = "uci",
    name: str = "iris",
    version: str = "1",
    schema_version: int = 1,
    sha256: str | None = None,
) -> dict[str, Any]:
    manifest = manifest_template()
    manifest.update(
        source=source,
        name=name,
        version=version,
        schema_version=schema_version,
    )
    if sha256 is not None:
        manifest["artifacts"][0]["sha256"] = sha256
    return manifest


def prepare_root(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "spec/schema", tmp_path / "spec/schema")


def make_release(
    root: Path,
    manifests: list[dict[str, Any]],
    defaults: list[dict[str, str]],
    *,
    release: str = "test",
    sequence: int = 0,
    errata: list[dict[str, Any]] | None = None,
) -> Path:
    manifest_directory = root / "manifests"
    manifest_directory.mkdir(exist_ok=True)
    paths = []
    for number, manifest in enumerate(manifests):
        path = manifest_directory / f"manifest-{number}.yaml"
        path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
        paths.append(str(path.relative_to(root)))

    erratum_paths = []
    for number, erratum in enumerate(errata or []):
        path = root / f"erratum-{number}.yaml"
        path.write_text(yaml.safe_dump(erratum, sort_keys=False), encoding="utf-8")
        erratum_paths.append(str(path.relative_to(root)))

    descriptor: dict[str, object] = {
        "schema_version": 1,
        "release": release,
        "sequence": sequence,
        "repository": "jolars/datamonger",
        "tag": release,
        "manifests": paths,
        "defaults": defaults,
    }
    if erratum_paths:
        descriptor["errata"] = erratum_paths
    release_path = root / "release.yaml"
    release_path.write_text(
        yaml.safe_dump(descriptor, sort_keys=False), encoding="utf-8"
    )
    return release_path


def default(version: str = "1") -> dict[str, str]:
    return {"source": "uci", "name": "iris", "version": version}


def test_valid_release_builds_and_validates_generated_documents(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    release_path = make_release(tmp_path, [make_manifest()], [default()])

    index_bytes, selector_bytes = dm_index.build(release_path, root=tmp_path)

    index = json.loads(index_bytes)
    selector = json.loads(selector_bytes)
    assert index_bytes.endswith(b"\n")
    assert selector_bytes.endswith(b"\n")
    assert (
        selector["index_sha256"]
        == __import__("hashlib").sha256(index_bytes).hexdigest()
    )
    assert index["datasets"][0]["source"] == "uci"


def write_release_outputs(release_path: Path, root: Path) -> None:
    index_bytes, selector_bytes = dm_index.build(release_path, root=root)
    (release_path.parent / "index.json").write_bytes(index_bytes)
    (release_path.parent / "selector.json").write_bytes(selector_bytes)


def test_catalog_is_generated_deterministically_from_release_selectors(
    tmp_path: Path,
) -> None:
    prepare_root(tmp_path)
    releases = tmp_path / "registry/releases"
    first_root = releases / "z-release"
    second_root = releases / "a-release"
    first_root.mkdir(parents=True)
    second_root.mkdir()
    first_path = make_release(
        tmp_path,
        [make_manifest()],
        [default()],
        release="z-release",
        sequence=0,
    )
    first_path.replace(first_root / "release.yaml")
    write_release_outputs(first_root / "release.yaml", tmp_path)
    second_path = make_release(
        tmp_path,
        [make_manifest()],
        [default()],
        release="a-release",
        sequence=1,
    )
    second_path.replace(second_root / "release.yaml")
    write_release_outputs(second_root / "release.yaml", tmp_path)

    contents = dm_index.build_catalog(root=tmp_path)
    catalog = json.loads(contents)

    assert contents.endswith(b"\n")
    assert [release["release"] for release in catalog["releases"]] == [
        "a-release",
        "z-release",
    ]
    dm_index._validate_schema(
        catalog,
        "catalog-v1.schema.json",
        tmp_path / "spec/schema",
        "catalog",
    )


def test_catalog_generation_rejects_stale_release_outputs(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    release_root = tmp_path / "registry/releases/release"
    release_root.mkdir(parents=True)
    release_path = make_release(tmp_path, [make_manifest()], [default()])
    release_path.replace(release_root / "release.yaml")
    write_release_outputs(release_root / "release.yaml", tmp_path)
    (release_root / "selector.json").write_bytes(b"stale")

    with pytest.raises(ValueError, match="release selector is stale"):
        dm_index.build_catalog(root=tmp_path)


def test_equivalent_source_trees_generate_identical_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    prepare_root(first)
    prepare_root(second)
    manifests = [make_manifest(version="2"), make_manifest(version="1")]
    first_release = make_release(first, manifests, [default("1")], release="equivalent")
    second_release = make_release(
        second, list(reversed(manifests)), [default("1")], release="equivalent"
    )

    assert dm_index.build(first_release, root=first) == dm_index.build(
        second_release, root=second
    )


def test_two_default_versions_for_one_dataset_are_rejected(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    release_path = make_release(
        tmp_path,
        [make_manifest(version="1"), make_manifest(version="2")],
        [default("1"), default("2")],
    )

    with pytest.raises(ValueError, match="at most one default"):
        dm_index.build(release_path, root=tmp_path)


@pytest.mark.parametrize(
    ("manifest", "message"),
    [
        (make_manifest(source="UCI"), "does not match"),
        (make_manifest(sha256="A" * 64), "does not match"),
        (make_manifest(schema_version=2), "schema_version"),
        (make_manifest() | {"surprise": True}, "Additional properties"),
    ],
)
def test_closed_manifest_schema_rejects_malformed_records(
    tmp_path: Path, manifest: dict[str, Any], message: str
) -> None:
    prepare_root(tmp_path)
    release_path = make_release(tmp_path, [manifest], [default()])

    with pytest.raises(ValueError, match=message):
        dm_index.build(release_path, root=tmp_path)


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    release_path = make_release(tmp_path, [make_manifest()], [default()])
    release_path.write_text(
        "release: test\nrelease: other\nrepository: jolars/datamonger\n"
        "tag: test\nmanifests: []\ndefaults: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate YAML"):
        dm_index.build(release_path, root=tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate-artifact", "unique name"),
        ("dangling-input", "unknown artifact"),
        ("wrong-delimiter", "format and delimiter"),
        ("policy-location", "upstream-only"),
        ("wrong-components", "declared columns"),
        ("dangling-task", "unknown component"),
    ],
)
def test_semantic_manifest_validation_rejects_cross_field_errors(
    tmp_path: Path, mutation: str, message: str
) -> None:
    prepare_root(tmp_path)
    manifest = make_manifest()
    if mutation == "duplicate-artifact":
        manifest["artifacts"].append(copy.deepcopy(manifest["artifacts"][0]))
    elif mutation == "dangling-input":
        manifest["representation"]["inputs"]["data"] = "missing"
    elif mutation == "wrong-delimiter":
        manifest["representation"]["options"]["delimiter"] = "\t"
    elif mutation == "policy-location":
        manifest["artifacts"][0]["downloads"][0]["kind"] = "mirror"
    elif mutation == "wrong-components":
        manifest["representation"]["expect"]["components"][0]["name"] = "wrong"
    else:
        manifest["tasks"][0]["target"] = "missing"
    release_path = make_release(tmp_path, [manifest], [default()])

    with pytest.raises(ValueError, match=message):
        dm_index.build(release_path, root=tmp_path)


def make_historical_release(root: Path, manifest: dict[str, Any]) -> None:
    release_root = root / "registry/releases/base"
    release_root.mkdir(parents=True)
    release_path = make_release(root, [manifest], [default()], release="base")
    release_path.replace(release_root / "release.yaml")
    index_bytes, _ = dm_index.build(release_root / "release.yaml", root=root)
    (release_root / "index.json").write_bytes(index_bytes)


def test_identity_bearing_mutation_is_rejected_against_history(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    make_historical_release(tmp_path, make_manifest())
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path,
        [make_manifest(sha256="0" * 64)],
        [default()],
        release="candidate",
        sequence=1,
    )
    release_path.replace(candidate_root / "release.yaml")

    with pytest.raises(ValueError, match="identity-bearing"):
        dm_index.build(candidate_root / "release.yaml", root=tmp_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [("task", "task"), ("verification", "append-only")],
)
def test_append_only_release_records_cannot_be_mutated_or_removed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    prepare_root(tmp_path)
    original = make_manifest()
    make_historical_release(tmp_path, original)
    candidate = copy.deepcopy(original)
    if mutation == "task":
        candidate["tasks"] = []
    else:
        candidate["representation"]["expect"]["verification"][0]["digest"] = "0" * 64
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path, [candidate], [default()], release="candidate", sequence=1
    )
    release_path.replace(candidate_root / "release.yaml")

    with pytest.raises(ValueError, match=message):
        dm_index.build(candidate_root / "release.yaml", root=tmp_path)


def test_release_may_append_tasks_and_verification_records(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    original = make_manifest()
    make_historical_release(tmp_path, original)
    candidate = copy.deepcopy(original)
    candidate["tasks"].append(
        {
            "name": "unsupervised",
            "type": "unsupervised",
            "features": ["sepal length", "sepal width"],
        }
    )
    candidate["representation"]["expect"]["verification"].append(
        {"canonical_form": 2, "algorithm": "sha256", "digest": "0" * 64}
    )
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path, [candidate], [default()], release="candidate", sequence=1
    )
    release_path.replace(candidate_root / "release.yaml")

    index_bytes, _ = dm_index.build(candidate_root / "release.yaml", root=tmp_path)

    dataset = json.loads(index_bytes)["datasets"][0]
    assert len(dataset["tasks"]) == 2
    assert len(dataset["representation"]["expect"]["verification"]) == 2


def test_newer_release_is_not_history_when_rechecking_an_older_release(
    tmp_path: Path,
) -> None:
    prepare_root(tmp_path)
    make_historical_release(tmp_path, make_manifest())
    newer_root = tmp_path / "registry/releases/newer"
    newer_root.mkdir()
    release_path = make_release(
        tmp_path,
        [make_manifest()],
        [default()],
        release="newer",
        sequence=1,
    )
    release_path.replace(newer_root / "release.yaml")

    base = tmp_path / "registry/releases/base/release.yaml"
    index_bytes, _ = dm_index.build(base, root=tmp_path)

    assert json.loads(index_bytes)["release"] == "base"


def test_approved_component_erratum_allows_exact_replacement(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    corrected = make_manifest()
    make_historical_release(tmp_path, corrected)
    history_path = tmp_path / "registry/releases/base/index.json"
    history = json.loads(history_path.read_bytes())
    old_component = copy.deepcopy(
        history["datasets"][0]["representation"]["expect"]["components"][0]
    )
    old_component["length"] = 151
    history["datasets"][0]["representation"]["expect"]["components"][0] = old_component
    history_path.write_text(json.dumps(history), encoding="utf-8")
    replacement = corrected["representation"]["expect"]["components"][0]
    erratum = {
        "schema_version": 1,
        "id": "iris-length",
        "release": "base",
        "dataset": default(),
        "target": {"kind": "component", "name": "sepal length"},
        "original": old_component,
        "replacement": replacement,
        "reason": "The published expected length was incorrect.",
        "approval": {"maintainer": "jolars", "approved_at": "2026-08-29"},
    }
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path,
        [corrected],
        [default()],
        release="candidate",
        sequence=1,
        errata=[erratum],
    )
    release_path.replace(candidate_root / "release.yaml")

    index_bytes, _ = dm_index.build(candidate_root / "release.yaml", root=tmp_path)

    assert json.loads(index_bytes)["errata"][0]["id"] == "iris-length"


def test_verification_erratum_replacement_must_match_target_key(
    tmp_path: Path,
) -> None:
    prepare_root(tmp_path)
    original = make_manifest()
    make_historical_release(tmp_path, original)
    candidate = copy.deepcopy(original)
    replacement = {
        "canonical_form": 2,
        "algorithm": "sha256",
        "digest": "0" * 64,
    }
    candidate["representation"]["expect"]["verification"].append(replacement)
    erratum = {
        "schema_version": 1,
        "id": "iris-verification",
        "release": "base",
        "dataset": default(),
        "target": {
            "kind": "verification",
            "canonical_form": 1,
            "algorithm": "sha256",
        },
        "original": original["representation"]["expect"]["verification"][0],
        "replacement": replacement,
        "reason": "The published digest was incorrect.",
        "approval": {"maintainer": "jolars", "approved_at": "2026-08-29"},
    }
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path,
        [candidate],
        [default()],
        release="candidate",
        sequence=1,
        errata=[erratum],
    )
    release_path.replace(candidate_root / "release.yaml")

    with pytest.raises(ValueError, match="replacement must match the target"):
        dm_index.build(candidate_root / "release.yaml", root=tmp_path)


def test_errata_preserve_authored_order(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    corrected = make_manifest()
    published = copy.deepcopy(corrected)
    published_components = published["representation"]["expect"]["components"]
    corrected_components = corrected["representation"]["expect"]["components"]
    for component in published_components:
        component["length"] += 1
    make_historical_release(tmp_path, published)
    erratum_ids = ["z-first", "a-second", "m-third", "n-fourth", "o-fifth"]
    errata = [
        {
            "schema_version": 1,
            "id": erratum_id,
            "release": "base",
            "dataset": default(),
            "target": {"kind": "component", "name": original["name"]},
            "original": original,
            "replacement": replacement,
            "reason": "The published expected length was incorrect.",
            "approval": {"maintainer": "jolars", "approved_at": "2026-08-29"},
        }
        for erratum_id, original, replacement in zip(
            erratum_ids,
            published_components,
            corrected_components,
            strict=True,
        )
    ]
    candidate_root = tmp_path / "registry/releases/candidate"
    candidate_root.mkdir()
    release_path = make_release(
        tmp_path,
        [corrected],
        [default()],
        release="candidate",
        sequence=1,
        errata=errata,
    )
    release_path.replace(candidate_root / "release.yaml")

    index_bytes, _ = dm_index.build(candidate_root / "release.yaml", root=tmp_path)

    assert [erratum["id"] for erratum in json.loads(index_bytes)["errata"]] == (
        erratum_ids
    )


@pytest.mark.parametrize("explicit_release", [False, True])
def test_cli_resolves_release_against_alternate_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_release: bool
) -> None:
    prepare_root(tmp_path)
    release_root = tmp_path / "registry/releases/proof-0001"
    release_root.mkdir(parents=True)
    release_path = make_release(
        tmp_path, [make_manifest()], [default()], release="proof-0001"
    )
    release_path.replace(release_root / "release.yaml")
    index_bytes, selector_bytes = dm_index.build(
        release_root / "release.yaml", root=tmp_path
    )
    (release_root / "index.json").write_bytes(index_bytes)
    (release_root / "selector.json").write_bytes(selector_bytes)
    (tmp_path / "registry/catalog.json").write_bytes(
        dm_index.build_catalog(root=tmp_path)
    )
    arguments = ["dm-index", "check"]
    if explicit_release:
        arguments.append("registry/releases/proof-0001/release.yaml")
    arguments.extend(["--root", str(tmp_path)])
    monkeypatch.setattr("sys.argv", arguments)

    assert dm_index.main() == 0


def test_cli_build_refreshes_production_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare_root(tmp_path)
    release_root = tmp_path / "registry/releases/proof-0001"
    release_root.mkdir(parents=True)
    release_path = make_release(
        tmp_path,
        [make_manifest()],
        [default()],
        release="proof-0001",
    )
    release_path.replace(release_root / "release.yaml")
    arguments = [
        "dm-index",
        "build",
        "registry/releases/proof-0001/release.yaml",
        "--root",
        str(tmp_path),
    ]
    monkeypatch.setattr("sys.argv", arguments)

    assert dm_index.main() == 0
    assert (
        json.loads((tmp_path / "registry/catalog.json").read_bytes())["releases"][0][
            "release"
        ]
        == "proof-0001"
    )


def test_cli_check_reports_stale_production_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    prepare_root(tmp_path)
    release_root = tmp_path / "registry/releases/proof-0001"
    release_root.mkdir(parents=True)
    release_path = make_release(
        tmp_path,
        [make_manifest()],
        [default()],
        release="proof-0001",
    )
    release_path.replace(release_root / "release.yaml")
    write_release_outputs(release_root / "release.yaml", tmp_path)
    (tmp_path / "registry/catalog.json").write_bytes(b"stale")
    arguments = [
        "dm-index",
        "check",
        "registry/releases/proof-0001/release.yaml",
        "--root",
        str(tmp_path),
    ]
    monkeypatch.setattr("sys.argv", arguments)

    assert dm_index.main() == 1
    assert "generated file is stale" in capsys.readouterr().err


def test_changed_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "index.json"
    target.write_bytes(b"old")

    with pytest.raises(ValueError, match="immutable"):
        dm_index._write_or_check(target, b"new", check=False)
    assert target.read_bytes() == b"old"


@pytest.mark.parametrize(
    ("release", "expected_digest"),
    [
        (
            ROOT / "registry/releases/proof-0001/release.yaml",
            "98cdbc7c8c795dcd021775de4c955c2442e6e1f2d7911e4c53b72327d90f6578",
        ),
        (
            ROOT / "tests/registry/releases/test-0001/release.yaml",
            "446d89ae6cc785a34688a7c83c19a6f45e0a115994081d0065452a16ff349253",
        ),
    ],
)
def test_checked_in_release_bytes_are_immutable(
    release: Path, expected_digest: str
) -> None:
    index_bytes, selector_bytes = dm_index.build(release, root=ROOT)

    assert index_bytes == (release.parent / "index.json").read_bytes()
    assert selector_bytes == (release.parent / "selector.json").read_bytes()
    assert __import__("hashlib").sha256(index_bytes).hexdigest() == expected_digest
