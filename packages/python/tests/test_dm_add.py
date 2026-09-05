from __future__ import annotations

import bz2
import copy
import gzip
import hashlib
import importlib.util
import sys
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
import yaml
from conftest import (
    EXPECTED_DIGEST,
    FIXTURE,
    LIBSVM_FIXTURE,
    LIBSVM_OPTIONS,
    LIBSVM_SPLIT_DIGEST,
    OPTIONS,
)

from datamonger.errors import RetrievalError

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("dm_add", TOOLS / "dm_add.py")
assert SPEC is not None and SPEC.loader is not None
dm_add = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dm_add
SPEC.loader.exec_module(dm_add)


@dataclass
class ServerState:
    bodies: dict[str, bytes] = field(default_factory=dict)
    headers: dict[str, dict[str, str | list[str]]] = field(default_factory=dict)
    requests: list[tuple[str, str | None]] = field(default_factory=list)


@pytest.fixture
def local_server() -> Iterator[tuple[str, ServerState]]:
    state = ServerState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests.append((self.path, self.headers.get("Accept-Encoding")))
            if self.path not in state.bodies:
                self.send_error(503)
                return
            body = state.bodies[self.path]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            for name, value in state.headers.get(self.path, {}).items():
                for item in value if isinstance(value, list) else [value]:
                    self.send_header(name, item)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}", state
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def delimited_draft(base_url: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "fixture",
        "name": "mixed",
        "version": "1",
        "title": "Mixed logical types",
        "description": "A small conformance dataset.",
        "modality": "tabular",
        "provenance": {
            "provider": "Datamonger",
            "upstream_name": "mixed",
            "landing_page": f"{base_url}/",
        },
        "license": {"status": "unknown"},
        "artifacts": [
            {
                "name": "data",
                "format": "csv",
                "compression": "none",
                "distribution": "upstream-only",
                "downloads": [{"kind": "upstream", "url": f"{base_url}/mixed.csv"}],
            }
        ],
        "representation": {
            "decoder": "delimited-text",
            "decoder_version": 1,
            "inputs": {"data": "data"},
            "options": copy.deepcopy(OPTIONS),
        },
        "tasks": [
            {
                "name": "default",
                "type": "classification",
                "features": ["measurement", "count", "label"],
                "target": "enabled",
            }
        ],
    }


def write_draft(tmp_path: Path, draft: dict[str, Any]) -> Path:
    path = tmp_path / "draft.yaml"
    path.write_text(yaml.safe_dump(draft, sort_keys=False), encoding="utf-8")
    return path


def test_build_derives_and_validates_delimited_manifest(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = contents

    result = dm_add.build(
        write_draft(tmp_path, delimited_draft(base_url)),
        root=ROOT,
        retrieved_at=date(2026, 9, 5),
    )

    artifact = result.manifest["artifacts"][0]
    assert artifact["size"] == len(contents)
    assert artifact["sha256"] == hashlib.sha256(contents).hexdigest()
    assert result.manifest["provenance"]["retrieved_at"] == "2026-09-05"
    assert result.manifest["representation"]["expect"] == {
        "components": [
            {
                "name": "measurement",
                "kind": "vector",
                "type": "float64",
                "length": 5,
            },
            {"name": "count", "kind": "vector", "type": "int64", "length": 5},
            {"name": "label", "kind": "vector", "type": "string", "length": 5},
            {"name": "enabled", "kind": "vector", "type": "bool", "length": 5},
        ],
        "verification": [
            {
                "canonical_form": 1,
                "algorithm": "sha256",
                "digest": EXPECTED_DIGEST,
            }
        ],
    }
    assert "measurement: vector float64 length=5" in result.report
    assert "<missing>" in result.report
    assert state.requests == [("/mixed.csv", "identity")]


def test_build_checks_every_location_and_rejects_disagreement(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.bodies.update({"/first.csv": contents, "/second.csv": contents})
    draft = delimited_draft(base_url)
    draft["artifacts"][0]["downloads"] = [
        {"kind": "upstream", "url": f"{base_url}/first.csv"},
        {"kind": "upstream", "url": f"{base_url}/second.csv"},
    ]

    dm_add.build(write_draft(tmp_path, draft), root=ROOT)

    assert [request[0] for request in state.requests] == [
        "/first.csv",
        "/second.csv",
    ]

    state.requests.clear()
    state.bodies["/second.csv"] = contents + b"changed"
    with pytest.raises(ValueError, match="does not match the other locations"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


@pytest.mark.parametrize("field", ["size", "sha256"])
def test_build_rejects_stale_derived_artifact_values(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    field: str,
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft = delimited_draft(base_url)
    draft["artifacts"][0][field] = 0 if field == "size" else "0" * 64

    with pytest.raises(ValueError, match=rf"artifact data {field}"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_build_accepts_matching_existing_derived_values(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = contents
    path = write_draft(tmp_path, delimited_draft(base_url))
    first = dm_add.build(path, root=ROOT, retrieved_at=date(2026, 9, 5))
    path.write_text(yaml.safe_dump(first.manifest, sort_keys=False), encoding="utf-8")

    second = dm_add.build(path, root=ROOT, retrieved_at=date(2026, 9, 6))

    assert second.manifest == first.manifest


def test_build_rejects_declared_compression_mismatch(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = gzip.compress(FIXTURE.read_bytes())
    draft = delimited_draft(base_url)

    with pytest.raises(ValueError, match=r"declares compression 'none'.*actually gzip"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


@pytest.mark.parametrize(
    ("compression", "compress"),
    [("gzip", gzip.compress), ("bzip2", bz2.compress)],
)
def test_build_hashes_compressed_artifact_before_decoding(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    compression: str,
    compress: Callable[[bytes], bytes],
) -> None:
    base_url, state = local_server
    contents = compress(FIXTURE.read_bytes())
    state.bodies["/mixed.csv"] = contents
    draft = delimited_draft(base_url)
    draft["artifacts"][0]["compression"] = compression

    result = dm_add.build(write_draft(tmp_path, draft), root=ROOT)

    artifact = result.manifest["artifacts"][0]
    assert artifact["size"] == len(contents)
    assert artifact["sha256"] == hashlib.sha256(contents).hexdigest()
    assert (
        result.manifest["representation"]["expect"]["verification"][0]["digest"]
        == EXPECTED_DIGEST
    )


def test_build_removes_ordinary_http_gzip_before_hashing(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = gzip.compress(contents)
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}

    result = dm_add.build(write_draft(tmp_path, delimited_draft(base_url)), root=ROOT)

    artifact = result.manifest["artifacts"][0]
    assert artifact["size"] == len(contents)
    assert artifact["sha256"] == hashlib.sha256(contents).hexdigest()


def test_build_rejects_mislabeled_content_encoding_hazard(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv.gz"] = gzip.compress(FIXTURE.read_bytes())
    state.headers["/mixed.csv.gz"] = {"Content-Encoding": "gzip"}
    draft = delimited_draft(base_url)
    artifact = draft["artifacts"][0]
    artifact["compression"] = "gzip"
    artifact["downloads"][0]["url"] = f"{base_url}/mixed.csv.gz"

    with pytest.raises(ValueError, match=r"Content-Encoding.*compression hazard"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_build_supports_libsvm_split_and_reports_sparse_samples(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    test_contents = (
        ROOT / "tests/conformance/artifacts/small-test.svmlight"
    ).read_bytes()
    state.bodies.update(
        {"/train.libsvm": LIBSVM_FIXTURE.read_bytes(), "/test.svmlight": test_contents}
    )
    draft = delimited_draft(base_url)
    draft["name"] = "small_split"
    draft["artifacts"] = [
        {
            "name": "train",
            "format": "libsvm",
            "compression": "none",
            "distribution": "upstream-only",
            "downloads": [{"kind": "upstream", "url": f"{base_url}/train.libsvm"}],
        },
        {
            "name": "test",
            "format": "svmlight",
            "compression": "none",
            "distribution": "upstream-only",
            "downloads": [{"kind": "upstream", "url": f"{base_url}/test.svmlight"}],
        },
    ]
    draft["representation"] = {
        "decoder": "libsvm-split",
        "decoder_version": 1,
        "inputs": {"train": "train", "test": "test"},
        "options": copy.deepcopy(LIBSVM_OPTIONS),
    }
    draft["tasks"] = [
        {
            "name": "default",
            "type": "classification",
            "splits": {
                "train": {
                    "features": "train_features",
                    "target": "train_response",
                },
                "test": {
                    "features": "test_features",
                    "target": "test_response",
                },
            },
        }
    ]

    result = dm_add.build(write_draft(tmp_path, draft), root=ROOT)

    expect = result.manifest["representation"]["expect"]
    assert [component["name"] for component in expect["components"]] == [
        "train_features",
        "train_response",
        "test_features",
        "test_response",
    ]
    assert expect["verification"][0]["digest"] == LIBSVM_SPLIT_DIGEST
    assert "train_features: sparse_matrix float64 rows=2 columns=4" in result.report
    assert "0:" in result.report


def test_build_rejects_stale_expectation(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft = delimited_draft(base_url)
    draft["representation"]["expect"] = {
        "components": [
            {"name": "wrong", "kind": "vector", "type": "int64", "length": 1}
        ],
        "verification": [
            {"canonical_form": 1, "algorithm": "sha256", "digest": "0" * 64}
        ],
    }

    with pytest.raises(ValueError, match=r"representation.expect does not match"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_build_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    path = tmp_path / "draft.yaml"
    path.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate YAML mapping key"):
        dm_add.build(path, root=ROOT)


def test_build_rejects_metadata_only_artifact(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, _ = local_server
    draft = delimited_draft(base_url)
    draft["artifacts"][0]["distribution"] = "metadata-only"

    with pytest.raises(ValueError, match="metadata-only"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_build_rejects_non_http_download(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, _ = local_server
    draft = delimited_draft(base_url)
    draft["artifacts"][0]["downloads"][0]["url"] = FIXTURE.as_uri()

    with pytest.raises(RetrievalError, match="unsupported retrieval URL scheme"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_build_reports_decoder_and_manifest_semantic_errors(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft = delimited_draft(base_url)
    draft["tasks"][0]["target"] = "unknown"

    with pytest.raises(ValueError, match="task refers to unknown component"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)

    draft = delimited_draft(base_url)
    draft["representation"]["decoder"] = "unknown"
    with pytest.raises(ValueError, match="dm-add supports"):
        dm_add.build(write_draft(tmp_path, draft), root=ROOT)


def test_cli_writes_yaml_and_summary_to_separate_streams(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft_path = write_draft(tmp_path, delimited_draft(base_url))
    monkeypatch.setattr("sys.argv", ["dm-add", str(draft_path)])

    assert dm_add.main() == 0

    captured = capsys.readouterr()
    output = yaml.safe_load(captured.out)
    assert output["representation"]["expect"]["verification"][0]["digest"] == (
        EXPECTED_DIGEST
    )
    assert "measurement: vector" in captured.err


def test_cli_refuses_to_replace_output_without_force(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft_path = write_draft(tmp_path, delimited_draft(base_url))
    output_path = tmp_path / "manifest.yaml"
    output_path.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv", ["dm-add", str(draft_path), "--output", str(output_path)]
    )

    assert dm_add.main() == 2
    assert output_path.read_text(encoding="utf-8") == "original\n"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "already exists" in captured.err
    assert state.requests == []


def test_cli_force_replaces_output_atomically(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url, state = local_server
    state.bodies["/mixed.csv"] = FIXTURE.read_bytes()
    draft_path = write_draft(tmp_path, delimited_draft(base_url))
    output_path = tmp_path / "manifest.yaml"
    output_path.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "dm-add",
            str(draft_path),
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert dm_add.main() == 0
    assert yaml.safe_load(output_path.read_text(encoding="utf-8"))["name"] == "mixed"
