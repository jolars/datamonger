"""Compile-time checks for the public return-type contract."""

from typing import assert_type

from datamonger import (
    DataInfo,
    DatasetData,
    FetchResult,
    Registry,
    SparseDataset,
    SparseDatasetSplit,
    data_info,
    fetch_data,
    list_data,
)


def check_fetch_data_return_types(registry: Registry, return_info: bool) -> None:
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
    assert_type(data_info("example", source="fixture", registry=registry), DataInfo)
    assert_type(list_data(registry=registry), tuple[DataInfo, ...])
