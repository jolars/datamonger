from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import sys
import threading
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from conftest import EXPECTED_DIGEST, FIXTURE, OPTIONS

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("dm_canary", TOOLS / "dm_canary.py")
assert SPEC is not None and SPEC.loader is not None
dm_canary = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dm_canary
SPEC.loader.exec_module(dm_canary)


@dataclass
class Response:
    body: bytes
    status: int = HTTPStatus.OK
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ServerState:
    responses: dict[str, Response] = field(default_factory=dict)
    requests: list[tuple[str, str | None]] = field(default_factory=list)


@pytest.fixture
def local_server() -> tuple[str, ServerState]:
    state = ServerState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests.append((self.path, self.headers.get("Accept-Encoding")))
            response = state.responses.get(self.path)
            if response is None:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self.send_response(response.status)
            self.send_header("Content-Length", str(len(response.body)))
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response.body)

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


def _dataset(
    base_url: str,
    contents: bytes,
    paths: list[str],
    *,
    compression: str = "none",
    canonical_digest: str = EXPECTED_DIGEST,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "fixture",
        "name": "mixed",
        "version": "1",
        "title": "Mixed logical types",
        "description": "A small canary dataset.",
        "modality": "tabular",
        "provenance": {
            "provider": "Datamonger",
            "upstream_name": "mixed",
            "landing_page": f"{base_url}/",
            "retrieved_at": "2026-09-05",
        },
        "license": {"status": "unknown"},
        "artifacts": [
            {
                "name": "data",
                "size": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
                "format": "csv",
                "compression": compression,
                "distribution": "upstream-only",
                "downloads": [
                    {"kind": "upstream", "url": f"{base_url}{path}"} for path in paths
                ],
            }
        ],
        "representation": {
            "decoder": "delimited-text",
            "decoder_version": 1,
            "inputs": {"data": "data"},
            "options": copy.deepcopy(OPTIONS),
            "expect": {
                "components": [
                    {
                        "name": "measurement",
                        "kind": "vector",
                        "type": "float64",
                        "length": 5,
                    },
                    {
                        "name": "count",
                        "kind": "vector",
                        "type": "int64",
                        "length": 5,
                    },
                    {
                        "name": "label",
                        "kind": "vector",
                        "type": "string",
                        "length": 5,
                    },
                    {
                        "name": "enabled",
                        "kind": "vector",
                        "type": "bool",
                        "length": 5,
                    },
                ],
                "verification": [
                    {
                        "canonical_form": 1,
                        "algorithm": "sha256",
                        "digest": canonical_digest,
                    }
                ],
            },
        },
    }


def _selector(
    tmp_path: Path,
    base_url: str,
    state: ServerState,
    datasets: list[dict[str, Any]],
) -> Path:
    index = {
        "schema_version": 1,
        "release": "test-0001",
        "defaults": [],
        "datasets": datasets,
    }
    index_bytes = (
        json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode()
    state.responses["/index.json"] = Response(index_bytes)
    selector = {
        "schema_version": 1,
        "release": "test-0001",
        "index_sha256": hashlib.sha256(index_bytes).hexdigest(),
        "index_url": f"{base_url}/index.json",
    }
    path = tmp_path / "selector.json"
    path.write_text(json.dumps(selector), encoding="utf-8")
    return path


def test_check_fetches_every_location_and_verifies_decoded_data(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.responses["/first.csv"] = Response(contents)
    state.responses["/second.csv"] = Response(contents)
    selector = _selector(
        tmp_path,
        base_url,
        state,
        [_dataset(base_url, contents, ["/first.csv", "/second.csv"])],
    )

    result = dm_canary.check(selector, root=ROOT)

    assert result.ok
    assert [(check.kind, check.ok) for check in result.checks] == [
        ("registry", True),
        ("location", True),
        ("location", True),
        ("dataset", True),
    ]
    assert state.requests == [
        ("/index.json", "identity"),
        ("/first.csv", "identity"),
        ("/second.csv", "identity"),
    ]
    assert "canonical SHA-256" in result.checks[-1].message
    assert "# Datamonger canary: PASSED" in result.render_markdown()


def test_check_aggregates_location_drift_and_still_decodes(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.responses["/good.csv"] = Response(contents)
    state.responses["/changed.csv"] = Response(contents.replace(b"1.5", b"1.6", 1))
    selector = _selector(
        tmp_path,
        base_url,
        state,
        [_dataset(base_url, contents, ["/good.csv", "/changed.csv", "/down.csv"])],
    )

    result = dm_canary.check(selector, root=ROOT)

    assert not result.ok
    failures = [check for check in result.checks if not check.ok]
    assert len(failures) == 2
    assert "SHA-256 mismatch" in failures[0].message
    assert "cannot retrieve" in failures[1].message
    dataset_check = next(check for check in result.checks if check.kind == "dataset")
    assert dataset_check.ok
    assert [request[0] for request in state.requests] == [
        "/index.json",
        "/good.csv",
        "/changed.csv",
        "/down.csv",
    ]
    report = result.render_markdown()
    assert "# Datamonger canary: FAILED" in report
    assert f"{base_url}/changed.csv" in report
    assert f"{base_url}/down.csv" in report


def test_check_reports_decoded_digest_drift_after_location_passes(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.responses["/mixed.csv"] = Response(contents)
    selector = _selector(
        tmp_path,
        base_url,
        state,
        [_dataset(base_url, contents, ["/mixed.csv"], canonical_digest="0" * 64)],
    )

    result = dm_canary.check(selector, root=ROOT)

    assert not result.ok
    assert result.checks[-2].kind == "location"
    assert result.checks[-2].ok
    assert result.checks[-1].kind == "dataset"
    assert not result.checks[-1].ok
    assert "decoded SHA-256 mismatch" in result.checks[-1].message


def test_check_names_mislabeled_content_encoding_hazard(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    compressed = gzip.compress(FIXTURE.read_bytes())
    state.responses["/mixed.csv.gz"] = Response(
        compressed, headers={"Content-Encoding": "gzip"}
    )
    selector = _selector(
        tmp_path,
        base_url,
        state,
        [
            _dataset(
                base_url,
                compressed,
                ["/mixed.csv.gz"],
                compression="gzip",
            )
        ],
    )

    result = dm_canary.check(selector, root=ROOT)

    location = next(check for check in result.checks if check.kind == "location")
    assert not location.ok
    assert "Content-Encoding removed declared gzip compression" in location.message


def test_check_decodes_a_multi_artifact_split(
    tmp_path: Path, local_server: tuple[str, ServerState]
) -> None:
    base_url, state = local_server
    fixture_index = json.loads(
        (ROOT / "tests/registry/releases/test-0002/index.json").read_bytes()
    )
    dataset = copy.deepcopy(
        next(
            candidate
            for candidate in fixture_index["datasets"]
            if candidate["name"] == "small_libsvm_split"
        )
    )
    source_paths = {
        "training-data": ROOT / "tests/conformance/artifacts/small.libsvm",
        "testing-data": ROOT / "tests/conformance/artifacts/small-test.svmlight",
    }
    for artifact in dataset["artifacts"]:
        artifact_name = artifact["name"]
        url_path = f"/{artifact_name}"
        artifact["downloads"] = [{"kind": "upstream", "url": f"{base_url}{url_path}"}]
        state.responses[url_path] = Response(source_paths[artifact_name].read_bytes())
    selector = _selector(tmp_path, base_url, state, [dataset])

    result = dm_canary.check(selector, root=ROOT)

    assert result.ok
    assert [(check.kind, check.ok) for check in result.checks] == [
        ("registry", True),
        ("location", True),
        ("location", True),
        ("dataset", True),
    ]
    assert result.checks[-1].message.endswith(
        "7169b3668489db5ab1f914ee7f2b102a01d31a55f21ce9b89fc88ce526670ead"
    )


def test_cli_returns_one_for_drift_and_two_for_invalid_invocation(
    tmp_path: Path,
    local_server: tuple[str, ServerState],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base_url, state = local_server
    contents = FIXTURE.read_bytes()
    state.responses["/changed.csv"] = Response(contents + b"changed")
    selector = _selector(
        tmp_path,
        base_url,
        state,
        [_dataset(base_url, contents, ["/changed.csv"])],
    )
    monkeypatch.setattr("sys.argv", ["dm-canary", str(selector)])

    assert dm_canary.main() == 1
    captured = capsys.readouterr()
    assert "# Datamonger canary: FAILED" in captured.out
    assert captured.err == ""

    monkeypatch.setattr("sys.argv", ["dm-canary", str(tmp_path / "missing.json")])
    assert dm_canary.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("dm-canary:")


def test_upstream_verification_workflow_is_scheduled_and_opens_issues() -> None:
    workflow = (ROOT / ".github/workflows/upstream-verification.yml").read_text(
        encoding="utf-8"
    )

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "issues: write" in workflow
    assert "tools/dm_canary.py" in workflow
    assert "gh issue create" in workflow
    assert "gh issue comment" in workflow
