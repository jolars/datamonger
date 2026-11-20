import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from conftest import CORPUS
from test_dm_index import dm_index
from test_splits import seed

from datamonger import (
    DatasetSplits,
    FetchResult,
    GraphDataset,
    HypergraphDataset,
    Registry,
    cache_info,
    data_info,
    fetch_data,
)
from datamonger.errors import (
    DecodedIntegrityError,
    DecodeError,
    OfflineError,
    UnsupportedDecoderError,
)

CASES = json.loads((CORPUS / "graphs.json").read_bytes())["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
@pytest.mark.parametrize("compression", ["none", "gzip", "bzip2"])
def test_graph_fetch(case: dict[str, Any], compression: str, tmp_path: Path) -> None:
    dm_index._validate_schema(
        case["manifest"],
        "manifest-v8.schema.json",
        CORPUS.parent.parent / "spec/schema",
        "manifest",
    )
    registry = seed(case, tmp_path, compression)
    result = fetch_data(
        case["id"],
        source="conformance",
        version="1",
        registry=registry,
        cache_dir=tmp_path,
        offline=True,
        return_info=True,
    )
    assert isinstance(result, FetchResult)
    assert (
        result.info.canonical_digest
        == hashlib.sha256(bytes.fromhex(case["expected_hex"])).hexdigest()
    )
    assert set(result.info.artifact_digests) == set(case["artifact_paths"])
    assert len(cache_info(cache_dir=tmp_path).entries) >= len(case["artifact_paths"])
    if case["id"] == "graph":
        assert isinstance(result.data, GraphDataset)
        assert result.data.nodes["id"].tolist() == [9007199254740993, 7]
        assert result.data.edges["source"].tolist() == [9007199254740993] * 2
    else:
        assert isinstance(result.data, HypergraphDataset)
        assert result.data.nodes["id"].tolist() == ["isolate", "inferred"]
        assert pd.isna(result.data.nodes["label"].iloc[1])
        assert result.data.hyperedges["id"].tolist() == [9007199254740993]


def test_graph_verification_and_recipe(tmp_path: Path) -> None:
    case = json.loads(json.dumps(CASES[0]))
    representation = case["manifest"]["representation"]
    representation["expect"]["verification"][0]["digest"] = "0" * 64
    registry = seed(case, tmp_path)
    opts = dict(source="conformance", version="1", cache_dir=tmp_path, offline=True)
    with pytest.raises(DecodedIntegrityError):
        fetch_data("graph", registry=registry, **opts)
    unchecked = fetch_data(
        "graph", registry=registry, verify_decoded=False, return_info=True, **opts
    )
    assert isinstance(unchecked, FetchResult)
    assert isinstance(unchecked.data, GraphDataset)
    assert unchecked.info.verification == "artifact"
    assert unchecked.info.canonical_digest is None
    representation["options"]["directed"] = 0
    with pytest.raises(UnsupportedDecoderError):
        fetch_data("graph", registry=seed(case, tmp_path), **opts)


@pytest.mark.parametrize(
    ("case_id", "role", "contents"),
    [
        ("graph", "edges", b"source,target\n7,8\n"),
        (
            "hif-undirected",
            "data",
            b'{"incidences":[{"node":"n","edge":1},{"node":"n","edge":1}]}',
        ),
    ],
)
def test_invalid_topology(
    case_id: str, role: str, contents: bytes, tmp_path: Path
) -> None:
    case = json.loads(json.dumps(next(case for case in CASES if case["id"] == case_id)))
    path = tmp_path / "invalid"
    path.write_bytes(contents)
    case["artifact_paths"][role] = str(path)
    registry = seed(case, tmp_path)
    with pytest.raises(DecodeError):
        fetch_data(
            f"conformance:{case_id}@1",
            registry=registry,
            cache_dir=tmp_path,
            offline=True,
            verify_decoded=False,
        )


def test_graph_artifact_and_component_failures(tmp_path: Path) -> None:
    case = json.loads(json.dumps(CASES[0]))
    case["manifest"]["representation"]["expect"]["components"][1]["length"] = 1
    registry = seed(case, tmp_path)
    args = dict(registry=registry, cache_dir=tmp_path, offline=True)
    with pytest.raises(DecodedIntegrityError):
        fetch_data("conformance:graph@1", **args)
    edge = case["manifest"]["artifacts"][1]
    path = tmp_path / "objects" / "sha256" / edge["sha256"]
    path.write_bytes(b"corrupt")
    with pytest.raises(OfflineError):
        fetch_data("conformance:graph@1", verify_decoded=False, **args)
    with pytest.raises(OfflineError):
        fetch_data("conformance:graph@1", **args)


def test_schema_eight_index_with_legacy_manifest(tmp_path: Path) -> None:
    registry = seed(CASES[0], tmp_path)
    directory = tmp_path / "registries" / "sha256"
    index = json.loads((directory / registry.index_sha256).read_bytes())
    legacy = json.loads((CORPUS / "named-splits.json").read_bytes())["cases"][0]
    seed(legacy, tmp_path)
    index["datasets"].append(legacy["manifest"])
    dm_index._validate_schema(
        index, "index-v8.schema.json", CORPUS.parent.parent / "spec/schema", "index"
    )
    payload = json.dumps(index).encode()
    digest = hashlib.sha256(payload).hexdigest()
    (directory / digest).write_bytes(payload)
    mixed = Registry(registry.release, digest, registry.index_url)
    result = fetch_data(
        f"conformance:{legacy['id']}@1",
        registry=mixed,
        cache_dir=tmp_path,
        offline=True,
    )
    assert isinstance(result, DatasetSplits)
    assert (
        data_info(
            "conformance:graph@1", registry=mixed, cache_dir=tmp_path, offline=True
        ).modality
        == "graph"
    )
    assert any(
        "conformance:graph@1" in entry.datasets
        for entry in cache_info(cache_dir=tmp_path).entries
    )
