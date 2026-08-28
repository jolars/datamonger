from __future__ import annotations

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
from scipy import sparse

from datamonger import FetchResult, Registry, SparseDataset, fetch_data
from datamonger.errors import (
    ArtifactIntegrityError,
    DecodedIntegrityError,
    RegistryIntegrityError,
    RegistryReleaseError,
    RetrievalError,
    UnknownDatasetError,
    UnsupportedRegistryError,
)

EXPECTED_DIGEST = "e25d27e8b0008332d778cd48429a7c4f7af59411884092e52f120da63f26e726"
FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"
LIBSVM_FIXTURE = Path(__file__).parent / "fixtures" / "small.libsvm"
LIBSVM_DIGEST = "50b077922f6ffc77054622fd807fbc8de48d1c3fcb3be644027422b244b0190b"


@dataclass
class ServerState:
    bodies: dict[str, bytes] = field(default_factory=dict)
    headers: dict[str, dict[str, str]] = field(default_factory=dict)
    online: bool = True
    requests: list[tuple[str, str | None]] = field(default_factory=list)


@pytest.fixture
def local_server() -> Iterator[tuple[str, ServerState]]:
    state = ServerState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requests.append((self.path, self.headers.get("Accept-Encoding")))
            if not state.online or self.path not in state.bodies:
                self.send_error(503)
                return
            body = state.bodies[self.path]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            for name, value in state.headers.get(self.path, {}).items():
                self.send_header(name, value)
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
                    "options": {
                        "encoding": "utf-8",
                        "delimiter": ",",
                        "header": True,
                        "quote": '"',
                        "escape": "double",
                        "missing_values": [""],
                        "row_order": "source",
                        "columns": [
                            {"name": "measurement", "type": "float64"},
                            {"name": "count", "type": "int64"},
                            {"name": "label", "type": "string"},
                            {"name": "enabled", "type": "bool"},
                        ],
                    },
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


def add_libsvm_dataset(
    base_url: str, state: ServerState, registry: Registry
) -> Registry:
    artifact = LIBSVM_FIXTURE.read_bytes()
    state.bodies["/small.libsvm"] = artifact
    index = json.loads(state.bodies["/index.json"])
    index["defaults"].append({"source": "fixture", "name": "sparse", "version": "1"})
    index["datasets"].append(
        {
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
                "options": {
                    "index_base": 1,
                    "feature_count": 4,
                    "duplicate_features": "error",
                    "label_type": "int64",
                    "row_order": "source",
                    "target_name": "response",
                },
                "expect": {
                    "components": [
                        {
                            "name": "features",
                            "kind": "sparse_matrix",
                            "type": "float64",
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

    with pytest.raises(RegistryIntegrityError, match="invalid expected"):
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


def test_nonidentity_content_coding_is_rejected(
    local_server: tuple[str, ServerState], tmp_path: Path
) -> None:
    base_url, state = local_server
    registry = make_registry(base_url, state)
    state.headers["/mixed.csv"] = {"Content-Encoding": "gzip"}

    with pytest.raises(RetrievalError, match="content coding"):
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
