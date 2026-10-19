from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_dm_index import dm_index, manifest_template

from datamonger import Registry, _api, data_info, list_data
from datamonger.errors import UnsupportedRegistryError

CASES = json.loads(
    (Path(__file__).parents[3] / "tests/conformance/preprocessing.json").read_bytes()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_preprocessing_contract(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = manifest_template()
    dataset["schema_version"] = case["manifest_schema_version"]
    if "preprocessing" in case:
        dataset["preprocessing"] = copy.deepcopy(case["preprocessing"])
    selected = Registry("preprocessing-test", "a" * 64, "https://example.invalid/index")
    index = {
        "schema_version": 3,
        "datasets": [dataset],
        "defaults": [{"source": "uci", "name": "iris", "version": "1"}],
    }
    monkeypatch.setattr(_api, "_load_registry", lambda *_args, **_kwargs: index)
    if case["expected"] == "invalid":
        with pytest.raises(ValueError):
            dm_index.validate_manifest(dataset)
        with pytest.raises(UnsupportedRegistryError):
            data_info("uci:iris@1", registry=selected, offline=True)
    else:
        dm_index.validate_manifest(dataset)
        info = data_info("uci:iris@1", registry=selected, offline=True)
        assert info.preprocessing == case.get("preprocessing")
        assert (
            list_data(registry=selected, offline=True)[0].preprocessing
            == info.preprocessing
        )


def test_preprocessing_requires_a_compatible_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = manifest_template()
    dataset["schema_version"] = 3
    index = {"schema_version": 2, "datasets": [dataset], "defaults": []}
    selected = Registry("test", "a" * 64, "https://example.invalid/index")
    monkeypatch.setattr(_api, "_load_registry", lambda *_args, **_kwargs: index)
    with pytest.raises(UnsupportedRegistryError):
        data_info("uci:iris@1", registry=selected)
