from __future__ import annotations

import gzip
import hashlib
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from conftest import (
    EXPECTED_DIGEST,
    FIXTURE,
    LIBSVM_DIGEST,
    LIBSVM_FIXTURE,
    LIBSVM_OPTIONS,
    OPTIONS,
)
from scipy import sparse

from datamonger import (
    BUNDLED_REGISTRY,
    FetchResult,
    Registry,
    SparseDataset,
    fetch_artifact,
    fetch_data,
)
from datamonger.errors import (
    ArtifactIntegrityError,
    DecodedIntegrityError,
    RegistryIntegrityError,
    RegistryReleaseError,
    RetrievalError,
    UnknownDatasetError,
    UnsupportedRegistryError,
)


@dataclass
class ServerState:
    bodies: dict[str, bytes] = field(default_factory=dict)
    headers: dict[str, dict[str, str | list[str]]] = field(default_factory=dict)
    online: bool = True
    requests: list[tuple[str, str | None]] = field(default_factory=list)
    chunked: set[str] = field(default_factory=set)
    redirects: dict[str, str] = field(default_factory=dict)
    truncate_content_length: set[str] = field(default_factory=set)
    truncate_chunked: set[str] = field(default_factory=set)


@pytest.fixture
def local_server() -> Iterator[tuple[str, ServerState]]:
    state = ServerState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests.append((self.path, self.headers.get("Accept-Encoding")))
            if self.path in state.redirects:
                self.send_response(302)
                self.send_header("Location", state.redirects[self.path])
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path in state.truncate_chunked:
                # Promise a chunk and close mid-stream so the client sees an
                # http.client.IncompleteRead.
                self.protocol_version = "HTTP/1.1"
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                self.wfile.write(b"ff\r\n0123")
                self.close_connection = True
                return
            if not state.online or self.path not in state.bodies:
                self.send_error(503)
                return
            body = state.bodies[self.path]
            if self.path in state.chunked:
                self.protocol_version = "HTTP/1.1"
                self.send_response(200)
                self.send_header("Transfer-Encoding", "chunked")
                for name, value in state.headers.get(self.path, {}).items():
                    for item in value if isinstance(value, list) else [value]:
                        self.send_header(name, item)
                self.end_headers()
                midpoint = len(body) // 2
                for chunk in (body[:midpoint], body[midpoint:]):
                    self.wfile.write(f"{len(chunk):x}\r\n".encode())
                    self.wfile.write(chunk + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
                return
            self.send_response(200)
            content_length = (
                len(body) + 1
                if self.path in state.truncate_content_length
                else len(body)
            )
            self.send_header("Content-Length", str(content_length))
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


def make_registry(
    base_url: str,
    state: ServerState,
    *,
    artifact_sha256: str | None = None,
    artifact_size: int | None = None,
    canonical_digest: str = EXPECTED_DIGEST,
    embedded_release: str = "proof-0001",
    schema_version: int = 1,
) -> Registry:
    artifact = FIXTURE.read_bytes()
    digest = artifact_sha256 or hashlib.sha256(artifact).hexdigest()
    state.bodies["/mixed.csv"] = artifact
    index: dict[str, Any] = {
        "schema_version": schema_version,
        "release": embedded_release,
        "defaults": [{"source": "fixture", "name": "mixed", "version": "1"}],
        "datasets": [
            {
                "schema_version": 1,
                "source": "fixture",
                "name": "mixed",
                "version": "1",
                "title": "Mixed logical types",
                "modality": "tabular",
                "artifacts": [
                    {
                        "name": "data",
                        "format": "csv",
                        "compression": "none",
                        "size": len(artifact)
                        if artifact_size is None
                        else artifact_size,
                        "sha256": digest,
                        "distribution": "upstream-only",
                        "downloads": [
                            {"kind": "upstream", "url": f"{base_url}/mixed.csv"}
                        ],
                    }
                ],
                "representation": {
                    "decoder": "delimited-text",
                    "decoder_version": 1,
                    "inputs": {"data": "data"},
                    "options": OPTIONS,
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
        ],
    }
    index_bytes = json.dumps(index, separators=(",", ":")).encode()
    state.bodies["/index.json"] = index_bytes
    return Registry(
        release="proof-0001",
        index_sha256=hashlib.sha256(index_bytes).hexdigest(),
        index_url=f"{base_url}/index.json",
    )


def test_fetch_data_uses_bundled_registry_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected: list[Registry] = []

    def record_registry(registry: Registry, cache_root: Path) -> dict[str, object]:
        selected.append(registry)
        raise UnknownDatasetError("stop after registry selection")

    monkeypatch.setattr("datamonger._api.load_registry", record_registry)

    monkeypatch.chdir(tmp_path)
    with pytest.raises(UnknownDatasetError, match="stop after registry selection"):
        fetch_data("iris", source="uci")

    assert selected == [BUNDLED_REGISTRY]


def add_libsvm_dataset(
    base_url: str, state: ServerState, registry: Registry
) -> Registry:
    artifact = LIBSVM_FIXTURE.read_bytes()
    state.bodies["/small.libsvm"] = artifact
    index = json.loads(state.bodies["/index.json"])
    index["defaults"].append({"source": "fixture", "name": "sparse", "version": "1"})
    index["datasets"].append(
        {
            "schema_version": 1,
            "source": "fixture",
            "name": "sparse",
            "version": "1",
            "title": "Small sparse fixture",
            "modality": "tabular",
            "artifacts": [
                {
                    "name": "data",
                    "format": "libsvm",
                    "compression": "none",
                    "size": len(artifact),
                    "sha256": hashlib.sha256(artifact).hexdigest(),
                    "distribution": "upstream-only",
                    "downloads": [
                        {"kind": "upstream", "url": f"{base_url}/small.libsvm"}
                    ],
                }
            ],
            "representation": {
                "decoder": "libsvm",
                "decoder_version": 1,
                "inputs": {"data": "data"},
                "options": LIBSVM_OPTIONS,
                "expect": {
                    "components": [
                        # DESIGN.md's normative sparse examples omit "type",
                        # so the fixture must be accepted without it.
                        {
                            "name": "features",
                            "kind": "sparse_matrix",
                            "rows": 2,
                            "columns": 4,
                        },
                        {
                            "name": "response",
                            "kind": "vector",
                            "type": "int64",
                            "length": 2,
                        },
                    ],
                    "verification": [
                        {
                            "canonical_form": 1,
                            "algorithm": "sha256",
                            "digest": LIBSVM_DIGEST,
                        }
                    ],
                },
            },
        }
    )
    index_bytes = json.dumps(index, separators=(",", ":")).encode()
    state.bodies["/index.json"] = index_bytes
    return Registry(
        release=registry.release,
        index_sha256=hashlib.sha256(index_bytes).hexdigest(),
        index_url=registry.index_url,
    )


def test_fetch_data_verifies_decodes_reports_and_reuses_cache_offline(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)

    first = fetch_data(
        "mixed",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )
    assert isinstance(first, FetchResult)
    assert first.info.dataset_id == "fixture:mixed@1"
    assert first.info.registry_release == "proof-0001"
    assert first.info.registry_index_sha256 == registry.index_sha256
    assert first.info.verification == "decoded"
    assert first.info.canonical_form == 1
    assert first.info.canonical_digest == EXPECTED_DIGEST
    assert all(encoding == "identity" for _, encoding in state.requests)

    state.online = False
    second = fetch_data(
        "mixed",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
    )
    pd.testing.assert_frame_equal(first.data, second)


def test_fetch_data_decodes_libsvm_to_sparse_dataset_and_reuses_it_offline(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = add_libsvm_dataset(base_url, state, make_registry(base_url, state))

    first = fetch_data(
        "sparse",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )

    assert isinstance(first, FetchResult)
    assert isinstance(first.data, SparseDataset)
    assert sparse.isspmatrix_csr(first.data.features)
    np.testing.assert_array_equal(
        first.data.features.toarray(),
        np.array([[1.5, 0.0, 0.0, -2.0], [0.0, 3.0, 0.0, 0.0]]),
    )
    np.testing.assert_array_equal(first.data.response, np.array([1, -1]))
    assert first.info.dataset_id == "fixture:sparse@1"
    assert first.info.verification == "decoded"
    assert first.info.canonical_digest == LIBSVM_DIGEST

    state.online = False
    second = fetch_data(
        "sparse", source="fixture", registry=registry, cache_dir=tmp_path
    )
    assert isinstance(second, SparseDataset)
    np.testing.assert_array_equal(
        second.features.toarray(), first.data.features.toarray()
    )
    np.testing.assert_array_equal(second.response, first.data.response)


def test_default_version_and_artifact_only_verification(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)

    result = fetch_data(
        "mixed",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
        verify_decoded=False,
        return_info=True,
    )

    assert isinstance(result, FetchResult)
    assert result.info.verification == "artifact"
    assert result.info.canonical_form is None
    assert result.info.canonical_digest is None


def test_registry_hash_is_checked_before_json_parsing(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    state.bodies["/index.json"] = b"not json"
    registry = Registry(
        release="proof-0001",
        index_sha256="0" * 64,
        index_url=f"{base_url}/index.json",
    )

    with pytest.raises(RegistryIntegrityError):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_malformed_registry_digest_cannot_be_used_as_a_cache_path(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, _ = local_server
    registry = Registry(
        release="proof-0001",
        index_sha256="../../outside",
        index_url=f"{base_url}/index.json",
    )

    with pytest.raises(RegistryIntegrityError, match="selector SHA-256"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )

    assert not (tmp_path.parent / "outside").exists()


def test_embedded_registry_release_must_match_selector(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, embedded_release="other")

    with pytest.raises(RegistryReleaseError):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_unsupported_registry_schema_is_rejected(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, schema_version=2)

    with pytest.raises(UnsupportedRegistryError, match="schema"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_unknown_dataset_and_version_are_distinguished_by_message(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)

    with pytest.raises(UnknownDatasetError, match="fixture:absent"):
        fetch_data(
            "absent",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )
    with pytest.raises(UnknownDatasetError, match="fixture:mixed@2"):
        fetch_data(
            "mixed",
            source="fixture",
            version="2",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_artifact_hash_mismatch_never_enters_cache(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, artifact_sha256="0" * 64)

    with pytest.raises(ArtifactIntegrityError):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )

    assert not (tmp_path / "objects" / "sha256" / ("0" * 64)).exists()


def test_artifact_size_mismatch_never_enters_cache(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, artifact_size=1)
    artifact_digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    with pytest.raises(ArtifactIntegrityError, match="size mismatch"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )

    assert not (tmp_path / "objects" / "sha256" / artifact_digest).exists()


def test_corrupt_cached_artifact_is_replaced_from_upstream(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    first = fetch_data("mixed", source="fixture", registry=registry, cache_dir=tmp_path)
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    cached_artifact = tmp_path / "objects" / "sha256" / digest
    cached_artifact.write_bytes(b"corrupt")

    second = fetch_data(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    pd.testing.assert_frame_equal(first, second)
    assert cached_artifact.read_bytes() == FIXTURE.read_bytes()


def test_corrupt_cached_registry_is_replaced_from_upstream(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    first = fetch_data("mixed", source="fixture", registry=registry, cache_dir=tmp_path)
    cached_registry = tmp_path / "registries" / "sha256" / registry.index_sha256
    expected_index = state.bodies["/index.json"]
    cached_registry.write_bytes(b"corrupt")

    second = fetch_data(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    pd.testing.assert_frame_equal(first, second)
    assert cached_registry.read_bytes() == expected_index


def test_declared_gzip_content_coding_is_removed_before_hashing(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    artifact = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = gzip.compress(artifact)
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}

    result = fetch_data(
        "mixed",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )

    assert isinstance(result, FetchResult)
    digest = hashlib.sha256(artifact).hexdigest()
    assert (tmp_path / "objects" / "sha256" / digest).read_bytes() == artifact


def test_gzip_content_is_decoded_and_hashed_incrementally(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    artifact = b"a" * (2 * 1024 * 1024 + 17)
    state.bodies["/mixed.csv"] = gzip.compress(artifact)
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}
    index = json.loads(state.bodies["/index.json"])
    record = index["datasets"][0]["artifacts"][0]
    record["size"] = len(artifact)
    record["sha256"] = hashlib.sha256(artifact).hexdigest()
    registry = _reseal_index(base_url, state, index)

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == artifact


@pytest.mark.parametrize("coding", ["identity", "IDENTITY"])
def test_identity_content_coding_preserves_artifact_bytes(
    coding: str,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Content-Encoding": coding}

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == FIXTURE.read_bytes()


@pytest.mark.parametrize("coding", ["x-gzip", "identity, gzip", "gzip, identity"])
def test_single_non_identity_gzip_coding_is_removed_before_hashing(
    coding: str,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    artifact = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = gzip.compress(artifact)
    state.headers["/mixed.csv"] = {"Content-Encoding": coding}

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == artifact


@pytest.mark.parametrize(
    "coding",
    ["", ",gzip", "gzip,", "gzip,,identity", "gzip; level=1"],
)
def test_malformed_content_coding_is_rejected(
    coding: str,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Content-Encoding": coding}

    with pytest.raises(RetrievalError, match="malformed HTTP content coding"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


@pytest.mark.parametrize(
    "coding",
    ["gzip, gzip", "gzip, x-gzip", ["gzip", "gzip"]],
    ids=["one-field", "aliases", "multiple-fields"],
)
def test_multiply_declared_content_coding_is_rejected(
    coding: str | list[str],
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Content-Encoding": coding}

    with pytest.raises(RetrievalError, match="multiple HTTP content codings"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


@pytest.mark.parametrize("mode", ["malformed", "truncated"])
def test_invalid_gzip_content_coding_stream_is_rejected(
    mode: str,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    coded = gzip.compress(FIXTURE.read_bytes())
    state.bodies["/mixed.csv"] = b"not gzip" if mode == "malformed" else coded[:-1]
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}

    with pytest.raises(RetrievalError, match=r"cannot retrieve|truncated gzip"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


@pytest.mark.parametrize(
    "coded",
    [
        gzip.compress(FIXTURE.read_bytes()) + gzip.compress(b"extra"),
        gzip.compress(FIXTURE.read_bytes()) + b"trailing garbage",
    ],
    ids=["concatenated", "trailing-data"],
)
def test_gzip_content_coding_rejects_data_after_the_first_stream(
    coded: bytes,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.bodies["/mixed.csv"] = coded
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}

    with pytest.raises(RetrievalError, match="data after gzip stream"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


def test_unknown_content_coding_is_rejected(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Content-Encoding": "br"}

    with pytest.raises(RetrievalError, match="content coding"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_truncated_chunked_response_is_a_retrieval_error(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.truncate_chunked.add("/mixed.csv")

    with pytest.raises(RetrievalError, match="cannot retrieve"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_chunked_transfer_framing_is_removed_before_hashing(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.chunked.add("/mixed.csv")

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == FIXTURE.read_bytes()


def test_chunked_transfer_framing_precedes_content_decoding(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    artifact = FIXTURE.read_bytes()
    state.bodies["/mixed.csv"] = gzip.compress(artifact)
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}
    state.chunked.add("/mixed.csv")

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == artifact


def test_redirected_response_uses_final_coding_and_identity_request(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    artifact = FIXTURE.read_bytes()
    state.redirects["/mixed.csv"] = "/redirected.csv"
    state.bodies["/redirected.csv"] = gzip.compress(artifact)
    state.headers["/redirected.csv"] = {"Content-Encoding": "gzip"}

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == artifact
    assert state.requests[-2:] == [
        ("/mixed.csv", "identity"),
        ("/redirected.csv", "identity"),
    ]


def test_truncated_content_length_response_is_a_retrieval_error(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.truncate_content_length.add("/mixed.csv")

    with pytest.raises(RetrievalError, match="truncated HTTP content"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


@pytest.mark.parametrize("coding", ["br", "gzip, chunked", "chunked, chunked"])
def test_unsupported_transfer_coding_is_rejected(
    coding: str,
    local_server: tuple[str, ServerState],
    tmp_path: Path,
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Transfer-Encoding": coding}

    with pytest.raises(RetrievalError, match="unsupported HTTP transfer coding"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)


def _reseal_index(base_url: str, state: ServerState, index: dict[str, Any]) -> Registry:
    index_bytes = json.dumps(index, separators=(",", ":")).encode()
    state.bodies["/index.json"] = index_bytes
    return Registry(
        release="proof-0001",
        index_sha256=hashlib.sha256(index_bytes).hexdigest(),
        index_url=f"{base_url}/index.json",
    )


def test_fetch_artifact_returns_verified_path_without_decoding(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, canonical_digest="0" * 64)

    artifact_path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert artifact_path == tmp_path / "objects" / "sha256" / digest
    assert artifact_path.read_bytes() == FIXTURE.read_bytes()


def test_fetch_artifact_requires_a_name_for_multi_artifact_dataset(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    extra = b"second artifact"
    state.bodies["/extra.bin"] = extra
    index = json.loads(state.bodies["/index.json"])
    index["datasets"][0]["artifacts"].append(
        {
            "name": "extra",
            "format": "svmlight",
            "compression": "gzip",
            "size": len(extra),
            "sha256": hashlib.sha256(extra).hexdigest(),
            "distribution": "mirror",
            "downloads": [{"kind": "mirror", "url": f"{base_url}/extra.bin"}],
        }
    )
    registry = _reseal_index(base_url, state, index)

    with pytest.raises(RetrievalError, match="available artifacts: data, extra"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)

    artifact_path = fetch_artifact(
        "mixed",
        source="fixture",
        artifact="extra",
        registry=registry,
        cache_dir=tmp_path,
    )
    assert artifact_path.read_bytes() == extra


def test_fetch_artifact_reports_unknown_name_and_available_artifacts(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)

    with pytest.raises(RetrievalError, match="available artifacts: data"):
        fetch_artifact(
            "mixed",
            source="fixture",
            artifact="absent",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_fetch_artifact_rejects_metadata_only_before_artifact_request(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    index = json.loads(state.bodies["/index.json"])
    artifact = index["datasets"][0]["artifacts"][0]
    artifact["distribution"] = "metadata-only"
    artifact["downloads"] = []
    registry = _reseal_index(base_url, state, index)

    with pytest.raises(RetrievalError, match="metadata-only"):
        fetch_artifact("mixed", source="fixture", registry=registry, cache_dir=tmp_path)

    assert [path for path, _ in state.requests] == ["/index.json"]


def test_fetch_artifact_tries_locations_in_manifest_order(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    state.bodies["/corrupt.csv"] = b"corrupt"
    index = json.loads(state.bodies["/index.json"])
    index["datasets"][0]["artifacts"][0]["downloads"] = [
        {"kind": "mirror", "url": f"{base_url}/absent.csv"},
        {"kind": "upstream", "url": f"{base_url}/corrupt.csv"},
        {"kind": "upstream", "url": f"{base_url}/mixed.csv"},
    ]
    registry = _reseal_index(base_url, state, index)

    artifact_path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert artifact_path.read_bytes() == FIXTURE.read_bytes()
    assert [path for path, _ in state.requests] == [
        "/index.json",
        "/absent.csv",
        "/corrupt.csv",
        "/mixed.csv",
    ]


def test_retrieval_falls_back_across_download_locations(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    index = json.loads(state.bodies["/index.json"])
    downloads = index["datasets"][0]["artifacts"][0]["downloads"]
    downloads.insert(0, {"kind": "upstream", "url": f"{base_url}/absent.csv"})
    registry = _reseal_index(base_url, state, index)

    result = fetch_data(
        "mixed",
        source="fixture",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )

    assert isinstance(result, FetchResult)
    assert result.info.verification == "decoded"


def test_retrieval_falls_back_after_invalid_content_coding(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    state.bodies["/bad-coding.csv"] = FIXTURE.read_bytes()
    state.headers["/bad-coding.csv"] = {"Content-Encoding": "br"}
    index = json.loads(state.bodies["/index.json"])
    downloads = index["datasets"][0]["artifacts"][0]["downloads"]
    downloads.insert(0, {"kind": "upstream", "url": f"{base_url}/bad-coding.csv"})
    registry = _reseal_index(base_url, state, index)

    path = fetch_artifact(
        "mixed", source="fixture", registry=registry, cache_dir=tmp_path
    )

    assert path.read_bytes() == FIXTURE.read_bytes()
    assert [request for request, _ in state.requests[-2:]] == [
        "/bad-coding.csv",
        "/mixed.csv",
    ]


def test_final_error_distinguishes_integrity_failure_from_unavailability(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    state.bodies["/corrupt.csv"] = b"corrupt"
    index = json.loads(state.bodies["/index.json"])
    index["datasets"][0]["artifacts"][0]["downloads"] = [
        {"kind": "upstream", "url": f"{base_url}/corrupt.csv"},
        {"kind": "upstream", "url": f"{base_url}/absent.csv"},
    ]
    registry = _reseal_index(base_url, state, index)

    with pytest.raises(ArtifactIntegrityError, match="all retrieval locations"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_unsupported_dataset_record_schema_is_rejected(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    make_registry(base_url, state)
    index = json.loads(state.bodies["/index.json"])
    index["datasets"][0]["schema_version"] = 2
    registry = _reseal_index(base_url, state, index)

    with pytest.raises(UnsupportedRegistryError, match="dataset schema"):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )


def test_decoded_digest_mismatch_is_distinct(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state, canonical_digest="0" * 64)

    with pytest.raises(DecodedIntegrityError):
        fetch_data(
            "mixed",
            source="fixture",
            registry=registry,
            cache_dir=tmp_path,
        )
