"""LIBSVM and SVMLight versions 1 and 2 decoding through datamonger-core."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

from scipy import sparse

from datamonger import _native
from datamonger._decoder_options import libsvm_options
from datamonger._models import (
    DecodedSparseDataset,
    DecodedSparseDatasetSplit,
    LogicalComponent,
    LogicalSparseMatrix,
    Pathish,
    ResponseArray,
    SparseDataset,
    SparseDatasetSplit,
)


def decode_libsvm(
    path: Pathish,
    options: Mapping[str, object],
    *,
    compression: str = "none",
    decoder_version: int = 1,
) -> DecodedSparseDataset:
    """Decode a strict LIBSVM or SVMLight version 1 or 2 representation."""

    feature_count, label_type, target_name = libsvm_options(options)
    matrix, response_component = cast(
        tuple[LogicalSparseMatrix, LogicalComponent],
        tuple(
            _native.decode_libsvm(
                Path(path),
                feature_count,
                label_type,
                target_name,
                compression,
                decoder_version,
            )
        ),
    )
    features = sparse.csr_matrix(
        (matrix.values, matrix.column_indices, matrix.row_offsets),
        shape=(matrix.rows, matrix.columns),
    )
    return DecodedSparseDataset(
        data=SparseDataset(
            features=features, response=cast(ResponseArray, response_component.values)
        ),
        components=(matrix, response_component),
    )


def decode_libsvm_split(
    train_path: Pathish,
    test_path: Pathish,
    options: Mapping[str, object],
    *,
    train_compression: str = "none",
    test_compression: str = "none",
    decoder_version: int = 1,
) -> DecodedSparseDatasetSplit:
    """Decode train and test inputs without concatenating either split."""

    train = decode_libsvm(
        train_path,
        options,
        compression=train_compression,
        decoder_version=decoder_version,
    )
    test = decode_libsvm(
        test_path,
        options,
        compression=test_compression,
        decoder_version=decoder_version,
    )
    train_features, train_response = train.components
    test_features, test_response = test.components
    components = (
        replace(train_features, name="train_features"),
        replace(train_response, name=f"train_{train_response.name}"),
        replace(test_features, name="test_features"),
        replace(test_response, name=f"test_{test_response.name}"),
    )
    return DecodedSparseDatasetSplit(
        data=SparseDatasetSplit(train=train.data, test=test.data),
        components=components,
    )
