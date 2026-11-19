"""LIBSVM and SVMLight versions 1 and 2 decoding through datamonger-core."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
from scipy import sparse

from datamonger import _native
from datamonger._decoder_options import libsvm_multilabel_options, libsvm_options
from datamonger._errors import UnsupportedDecoderError
from datamonger._models import (
    DecodedMultilabelSparseDataset,
    DecodedRankingSparseDataset,
    DecodedSparseDataset,
    DecodedSparseDatasetSplit,
    LogicalComponent,
    LogicalSparseMatrix,
    MultilabelSparseDataset,
    Pathish,
    RankingSparseDataset,
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
    compute_digest: bool = False,
) -> DecodedSparseDataset:
    """Decode a strict LIBSVM or SVMLight version 1 or 2 representation."""

    components, digest = _native.decode_libsvm(
        (Path(path), compression),
        None,
        libsvm_options(options),
        decoder_version,
        compute_digest,
    )
    pair = cast(tuple[LogicalSparseMatrix, LogicalComponent], tuple(components))
    return DecodedSparseDataset(_sparse_dataset(*pair), pair, digest)


def _sparse_dataset(
    matrix: LogicalSparseMatrix, response: LogicalComponent
) -> SparseDataset:
    return SparseDataset(_csr(matrix), cast(ResponseArray, response.values))


def _csr(matrix: LogicalSparseMatrix) -> sparse.csr_matrix:
    return sparse.csr_matrix(
        (matrix.values, matrix.column_indices, matrix.row_offsets),
        shape=(matrix.rows, matrix.columns),
    )


def decode_libsvm_split(
    train_path: Pathish,
    test_path: Pathish,
    options: Mapping[str, object],
    *,
    train_compression: str = "none",
    test_compression: str = "none",
    decoder_version: int = 1,
    compute_digest: bool = False,
) -> DecodedSparseDatasetSplit:
    """Decode train and test inputs without concatenating either split."""

    components, digest = _native.decode_libsvm(
        (Path(train_path), train_compression),
        (Path(test_path), test_compression),
        libsvm_options(options),
        decoder_version,
        compute_digest,
    )
    split = cast(
        tuple[
            LogicalSparseMatrix, LogicalComponent, LogicalSparseMatrix, LogicalComponent
        ],
        tuple(components),
    )
    return DecodedSparseDatasetSplit(
        data=SparseDatasetSplit(
            train=_sparse_dataset(split[0], split[1]),
            test=_sparse_dataset(split[2], split[3]),
        ),
        components=split,
        canonical_digest=digest,
    )


def decode_libsvm_multilabel(
    path: Pathish,
    options: Mapping[str, object],
    *,
    compression: str = "none",
    compute_digest: bool = False,
) -> DecodedMultilabelSparseDataset:
    recipe = libsvm_multilabel_options(options)
    components, digest = _native.decode_libsvm_multilabel(
        Path(path), compression, recipe, compute_digest
    )
    pair = cast(tuple[LogicalSparseMatrix, LogicalSparseMatrix], tuple(components))
    return DecodedMultilabelSparseDataset(
        MultilabelSparseDataset(_csr(pair[0]), _csr(pair[1]), recipe[2]), pair, digest
    )


def decode_svmlight_ranking(
    path: Pathish,
    options: Mapping[str, object],
    *,
    compression: str = "none",
    compute_digest: bool = False,
) -> DecodedRankingSparseDataset:
    base = options.get("index_base")
    if (
        type(base) is not int
        or base not in (0, 1)
        or options.get("target_name") == "query_id"
    ):
        raise UnsupportedDecoderError("invalid SVMLight ranking options")
    count, label_type, target = libsvm_options({**options, "index_base": 1})
    components, digest = _native.decode_svmlight_ranking(
        Path(path), compression, (count, base, label_type, target), compute_digest
    )
    logical = cast(
        tuple[LogicalSparseMatrix, LogicalComponent, LogicalComponent],
        tuple(components),
    )
    matrix, label, query = logical
    return DecodedRankingSparseDataset(
        RankingSparseDataset(
            _csr(matrix),
            cast(ResponseArray, label.values),
            cast(npt.NDArray[np.int64], query.values),
        ),
        logical,
        digest,
    )
