"""Compile-time checks for the public return-type contract."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, assert_type

import pandas as pd

from datamonger import (
    DataInfo,
    DatasetData,
    DatasetSplits,
    FetchResult,
    Registry,
    SparseDataset,
    SparseDatasetSplit,
    cite_data,
    data_info,
    fetch_artifact,
    fetch_data,
    list_data,
)


def check_fetch_data_return_types(registry: Registry, return_info: bool) -> None:
    assert_type(fetch_data("fixture:example", registry=registry), DatasetData)
    assert_type(
        fetch_data("fixture:example@1", registry=registry, return_info=True),
        FetchResult,
    )
    assert_type(
        fetch_data("fixture:example", registry=registry, return_info=return_info),
        DatasetData | FetchResult,
    )
    assert_type(fetch_data("example", source="fixture", registry=registry), DatasetData)
    assert_type(
        fetch_data("example", source="fixture", registry=registry, return_info=False),
        DatasetData,
    )
    assert_type(
        fetch_data("example", source="fixture", registry=registry, return_info=True),
        FetchResult,
    )
    assert_type(
        fetch_data(
            "example",
            source="fixture",
            registry=registry,
            return_info=return_info,
        ),
        DatasetData | FetchResult,
    )


def check_sparse_result_structure(
    dataset: SparseDataset, split: SparseDatasetSplit
) -> None:
    assert_type(split.train, SparseDataset)
    assert_type(split.test, SparseDataset)
    assert_type(dataset, SparseDataset)


def check_metadata_return_types(registry: Registry) -> None:
    assert_type(data_info("fixture:example@1", registry=registry), DataInfo)
    assert_type(fetch_artifact("fixture:example@1", registry=registry), Path)
    assert_type(data_info("example", source="fixture", registry=registry), DataInfo)
    assert_type(list_data(registry=registry), tuple[DataInfo, ...])


def check_named_split_structure(data: DatasetSplits) -> None:
    assert_type(data["validation"], pd.DataFrame | SparseDataset)


def check_citation_return_types(registry: Registry) -> None:
    assert_type(cite_data("fixture:example", registry=registry), str)
    assert_type(
        cite_data("fixture:example", registry=registry, format="records"),
        tuple[Mapping[str, Any], ...],
    )
