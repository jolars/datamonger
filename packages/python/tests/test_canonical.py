from __future__ import annotations

import hashlib
import math

import pytest

from datamonger._canonical import canonical_bytes, canonical_sha256
from datamonger._models import LogicalComponent, LogicalSparseMatrix


def test_int64_vector_has_exact_provisional_encoding() -> None:
    component = LogicalComponent(
        name="count",
        logical_type="int64",
        values=(1, 999, -2),
        valid=(True, False, True),
    )

    expected = bytes.fromhex(
        "444d4346"  # DMCF
        "0100"  # version
        "01000000"  # component count
        "05000000"  # name length
        "636f756e74"  # count
        "01"  # vector
        "02"  # int64
        "01"  # rank
        "0300000000000000"  # length
        "05"  # validity
        "0100000000000000"
        "0000000000000000"
        "feffffffffffffff"
    )

    assert canonical_bytes((component,)) == expected
    assert canonical_sha256((component,)) == hashlib.sha256(expected).hexdigest()


def test_float_encoding_normalizes_negative_zero_nan_and_invalid_storage() -> None:
    component = LogicalComponent(
        name="x",
        logical_type="float64",
        values=(-0.0, math.nan, 123.0),
        valid=(True, True, False),
    )

    encoded = canonical_bytes((component,))

    assert encoded[-24:] == bytes.fromhex(
        "0000000000000000"  # normalized negative zero
        "000000000000f87f"  # canonical quiet NaN
        "0000000000000000"  # invalid storage
    )


def test_bool_padding_and_invalid_bits_are_zero() -> None:
    component = LogicalComponent(
        name="flag",
        logical_type="bool",
        values=(True, True, True, True, True),
        valid=(True, False, True, True, True),
    )

    encoded = canonical_bytes((component,))

    assert encoded[-2:] == bytes((0b00011101, 0b00011101))


def test_float64_csr_matrix_has_exact_provisional_encoding() -> None:
    component = LogicalSparseMatrix(
        name="features",
        rows=2,
        columns=4,
        row_offsets=(0, 2, 3),
        column_indices=(0, 3, 1),
        values=(1.5, -2.0, 3.0),
    )

    expected = bytes.fromhex(
        "444d4346"  # DMCF
        "0100"  # version
        "01000000"  # component count
        "08000000"  # name length
        "6665617475726573"  # features
        "02"  # sparse matrix
        "01"  # float64
        "02"  # rank
        "0200000000000000"  # rows
        "0400000000000000"  # columns
        "0300000000000000"  # nonzero count
        "0000000000000000"  # row offsets
        "0200000000000000"
        "0300000000000000"
        "0000000000000000"  # column indices
        "0300000000000000"
        "0100000000000000"
        "000000000000f83f"  # values
        "00000000000000c0"
        "0000000000000840"
    )

    assert canonical_bytes((component,)) == expected
    assert canonical_sha256((component,)) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize(
    "component",
    [
        LogicalSparseMatrix("x", 1, 2, (0, 2), (0, 0), (1.0, 2.0)),
        LogicalSparseMatrix("x", 1, 2, (0, 1), (2,), (1.0,)),
        LogicalSparseMatrix("x", 1, 2, (0, 1), (0,), (0.0,)),
        LogicalSparseMatrix("x", 1, 2, (1, 1), (), ()),
    ],
)
def test_sparse_encoding_rejects_noncanonical_csr(
    component: LogicalSparseMatrix,
) -> None:
    with pytest.raises(ValueError):
        canonical_bytes((component,))
