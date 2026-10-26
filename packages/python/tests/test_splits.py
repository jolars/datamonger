from __future__ import annotations

import bz2
import copy
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from conftest import CORPUS
from test_dm_index import dm_index, make_release, prepare_root

from datamonger import DatasetSplits, FetchResult, Registry, SparseDataset, fetch_data
from datamonger._canonical import canonical_bytes
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm
from datamonger._splits import assemble_splits
from datamonger.errors import DecodedIntegrityError, UnsupportedDecoderError

DOCUMENT = json.loads((CORPUS / "named-splits.json").read_bytes())


def test_named_split_registry_build(tmp_path: Path) -> None:
    prepare_root(tmp_path)
    dataset = copy.deepcopy(DOCUMENT["cases"][0]["manifest"])
    release = make_release(
        tmp_path,
        [dataset],
        [{"source": "conformance", "name": dataset["name"], "version": "1"}],
    )
    index_bytes, _ = dm_index.build(release, root=tmp_path)
    index = json.loads(index_bytes)
    assert index["schema_version"] == 4
    assert index["datasets"] == [dataset]


def seed(case: dict[str, Any], cache: Path, compression: str = "none") -> Registry:
    dataset = copy.deepcopy(case["manifest"])
    objects = cache / "objects/sha256"
    objects.mkdir(parents=True, exist_ok=True)
    for artifact in dataset["artifacts"]:
        contents = (CORPUS / case["artifact_paths"][artifact["name"]]).read_bytes()
        if compression == "gzip":
            contents = gzip.compress(contents, mtime=0)
        elif compression == "bzip2":
            contents = bz2.compress(contents)
        artifact.update(
            compression=compression,
            size=len(contents),
            sha256=hashlib.sha256(contents).hexdigest(),
        )
        (objects / artifact["sha256"]).write_bytes(contents)
    index = {
        "schema_version": dataset["schema_version"],
        "release": "named-splits-test",
        "datasets": [dataset],
        "defaults": [],
    }
    contents = json.dumps(index, ensure_ascii=False).encode()
    digest = hashlib.sha256(contents).hexdigest()
    registries = cache / "registries/sha256"
    registries.mkdir(parents=True, exist_ok=True)
    (registries / digest).write_bytes(contents)
    return Registry(index["release"], digest, "https://example.invalid/index")


@pytest.mark.parametrize("case", DOCUMENT["cases"], ids=lambda c: c["id"])
@pytest.mark.parametrize("compression", ["none", "gzip", "bzip2"])
def test_named_splits_public_fetch(
    case: dict[str, Any], compression: str, tmp_path: Path
) -> None:
    dm_index.validate_manifest(case["manifest"])
    registry = seed(case, tmp_path, compression)
    result = fetch_data(
        case["manifest"]["name"],
        source="conformance",
        version="1",
        registry=registry,
        cache_dir=tmp_path,
        offline=True,
        return_info=True,
    )
    assert isinstance(result, FetchResult)
    assert isinstance(result.data, DatasetSplits)
    assert list(result.data) == [s["name"] for s in case["expected_splits"]]
    assert (
        result.info.canonical_digest
        == hashlib.sha256(bytes.fromhex(case["expected_hex"])).hexdigest()
    )
    assert result.info.verification == "decoded"
    assert set(result.info.artifact_digests) == set(case["artifact_paths"])
    for expected in case["expected_splits"]:
        split = result.data[expected["name"]]
        if expected["kind"] == "sparse":
            assert isinstance(split, SparseDataset)
            assert split.features.toarray().tolist() == expected["features"]
            assert split.response.tolist() == expected["response"]
        else:
            assert isinstance(split, pd.DataFrame)
            assert list(split.columns) == expected["columns"]
            assert {c: split[c].tolist() for c in split} == expected["values"]

    unchecked = fetch_data(
        f"conformance:{case['id']}@1",
        registry=registry,
        cache_dir=tmp_path,
        offline=True,
        verify_decoded=False,
        return_info=True,
    )
    assert isinstance(unchecked.data, DatasetSplits)
    assert list(unchecked.data) == list(result.data)
    assert unchecked.info.verification == "artifact"
    assert unchecked.info.canonical_digest is None


@pytest.mark.parametrize("case", DOCUMENT["cases"], ids=lambda c: c["id"])
def test_named_split_canonical_bytes(case: dict[str, Any]) -> None:
    manifest = case["manifest"]
    representation = manifest["representation"]
    recipes = representation["options"]["splits"]
    children = []
    for recipe in recipes:
        artifact = representation["inputs"][recipe["name"]]
        path = CORPUS / case["artifact_paths"][artifact]
        decoder = (
            decode_libsvm if recipe["decoder"] == "libsvm" else decode_delimited_text
        )
        children.append(decoder(path, recipe["options"]))
    assembled = assemble_splits(recipes, children)
    assert canonical_bytes(assembled.components).hex() == case["expected_hex"]


@pytest.mark.parametrize("invalid", DOCUMENT["invalid"], ids=lambda c: c["id"])
def test_invalid_named_split_recipes(invalid: dict[str, Any], tmp_path: Path) -> None:
    case = copy.deepcopy(DOCUMENT["cases"][0])
    case["manifest"]["representation"] = invalid["representation"]
    with pytest.raises(ValueError):
        dm_index.validate_manifest(case["manifest"])
    registry = seed(case, tmp_path)
    with pytest.raises(UnsupportedDecoderError):
        fetch_data(
            "conformance:three-provider-splits@1",
            registry=registry,
            cache_dir=tmp_path,
            offline=True,
        )


@pytest.mark.parametrize("mutation", ["order", "membership", "shape", "missing-labels"])
def test_named_splits_verification_detects_changes(
    mutation: str, tmp_path: Path
) -> None:
    case = copy.deepcopy(DOCUMENT["cases"][0])
    representation = case["manifest"]["representation"]
    if mutation == "order":
        representation["options"]["splits"].reverse()
    elif mutation == "membership":
        representation["inputs"]["validation"] = representation["inputs"]["train"]
    elif mutation == "shape":
        representation["expect"]["components"][0]["rows"] += 1
    else:
        representation["expect"]["components"].pop()
    registry = seed(case, tmp_path)
    with pytest.raises(DecodedIntegrityError):
        fetch_data(
            "conformance:three-provider-splits@1",
            registry=registry,
            cache_dir=tmp_path,
            offline=True,
        )


@pytest.mark.parametrize(
    "mutation", ["cross-split", "no-target", "unknown-split", "old-schema"]
)
def test_named_split_metadata_validation(mutation: str) -> None:
    dataset = copy.deepcopy(DOCUMENT["cases"][0]["manifest"])
    roles = dataset["tasks"][0]["splits"]
    if mutation == "cross-split":
        roles["test"]["features"] = "train/features"
    elif mutation == "no-target":
        for split in roles.values():
            split.pop("target", None)
    elif mutation == "unknown-split":
        roles["other"] = roles.pop("test")
    else:
        dataset["schema_version"] = 3
    with pytest.raises(ValueError):
        dm_index.validate_manifest(dataset)


def test_named_splits_can_select_libsvm_v2(tmp_path: Path) -> None:
    case = copy.deepcopy(DOCUMENT["cases"][0])
    case["manifest"]["schema_version"] = 5
    for recipe in case["manifest"]["representation"]["options"]["splits"]:
        if recipe["decoder"] == "libsvm":
            recipe["decoder_version"] = 2
    dm_index.validate_manifest(case["manifest"])
    registry = seed(case, tmp_path)
    result = fetch_data(
        case["manifest"]["name"],
        source="conformance",
        version="1",
        registry=registry,
        cache_dir=tmp_path,
        offline=True,
        return_info=True,
    )
    assert (
        result.info.canonical_digest
        == case["manifest"]["representation"]["expect"]["verification"][0]["digest"]
    )
