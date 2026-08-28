from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from datamonger import FetchResult, Registry, SparseDataset, fetch_data

ROOT = Path(__file__).resolve().parents[3]
SELECTOR = ROOT / "registry" / "releases" / "proof-0001" / "selector.json"


def _registry() -> Registry:
    selector = json.loads(SELECTOR.read_text(encoding="utf-8"))
    return Registry(**selector)


def test_published_proof_registry_fetches_and_verifies_real_datasets(
    tmp_path: Path,
) -> None:
    registry = _registry()

    iris = fetch_data(
        "iris",
        source="uci",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )
    assert isinstance(iris, FetchResult)
    assert isinstance(iris.data, pd.DataFrame)
    assert iris.data.shape == (150, 5)
    assert iris.data["class"].value_counts().to_dict() == {
        "Iris-setosa": 50,
        "Iris-versicolor": 50,
        "Iris-virginica": 50,
    }
    assert iris.info.dataset_id == "uci:iris@1"
    assert iris.info.verification == "decoded"
    assert iris.info.registry_index_sha256 == registry.index_sha256

    heart = fetch_data(
        "heart_scale",
        source="libsvm",
        registry=registry,
        cache_dir=tmp_path,
        return_info=True,
    )
    assert isinstance(heart, FetchResult)
    assert isinstance(heart.data, SparseDataset)
    assert heart.data.features.shape == (270, 13)
    assert heart.data.features.nnz == 3378
    assert np.count_nonzero(heart.data.response == 1) == 120
    assert np.count_nonzero(heart.data.response == -1) == 150
    assert heart.info.dataset_id == "libsvm:heart_scale@1"
    assert heart.info.verification == "decoded"
    assert heart.info.registry_index_sha256 == registry.index_sha256
