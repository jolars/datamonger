from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from datamonger._canonical import canonical_bytes, canonical_sha256
from datamonger._models import (
    LogicalComponent,
    LogicalDenseMatrix,
    LogicalSparseMatrix,
)

CORPUS = Path(__file__).resolve().parents[3] / "tests/conformance/canonical/cases.json"
GOLDEN_CASES = json.loads(CORPUS.read_bytes())["cases"]


def component_from_case(case: dict[str, Any]) -> object:
    component = case["component"]
    kind = component["kind"]
    if kind == "sparse_matrix":
        return LogicalSparseMatrix(
            component["name"],
            component["rows"],
            component["columns"],
            component["row_offsets"],
            component["column_indices"],
            component["values"],
        )
    values = component["values"]
    if case["id"] == "float64-dense-normalization":
        values = (-0.0, math.nan, 123.0, 4.5)
    if kind == "dense_matrix":
        return LogicalDenseMatrix(
            component["name"],
            cast(Any, component["type"]),
            component["rows"],
            component["columns"],
            values,
            component["valid"],
        )
    return LogicalComponent(
        component["name"],
        cast(Any, component["type"]),
        values,
        component["valid"],
    )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda case: case["id"])
def test_language_neutral_canonical_golden_cases(case: dict[str, Any]) -> None:
    component = cast(Any, component_from_case(case))

    assert canonical_bytes((component,)) == bytes.fromhex(case["expected_hex"])


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


def test_sparse_component_accepts_numpy_arrays_with_identical_encoding() -> None:
    from_tuples = LogicalSparseMatrix(
        "features", 2, 4, (0, 2, 3), (0, 3, 1), (1.5, -2.0, 3.0)
    )
    from_arrays = LogicalSparseMatrix(
        "features",
        2,
        4,
        np.asarray([0, 2, 3], dtype=np.int64),
        np.asarray([0, 3, 1], dtype=np.int64),
        np.asarray([1.5, -2.0, 3.0], dtype=np.float64),
    )

    assert canonical_bytes((from_arrays,)) == canonical_bytes((from_tuples,))


def test_sparse_nan_values_are_normalized_to_the_canonical_quiet_nan() -> None:
    component = LogicalSparseMatrix("x", 1, 1, (0, 1), (0,), (math.nan,))

    encoded = canonical_bytes((component,))

    assert encoded[-8:] == bytes.fromhex("000000000000f87f")


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


def test_float64_dense_matrix_matches_language_neutral_golden_bytes() -> None:
    cases = json.loads(CORPUS.read_bytes())["cases"]
    case = next(case for case in cases if case["id"] == "float64-dense-normalization")
    component = LogicalDenseMatrix(
        name="x",
        logical_type="float64",
        rows=2,
        columns=2,
        values=(-0.0, math.nan, 123.0, 4.5),
        valid=(True, True, False, True),
    )

    assert canonical_bytes((component,)) == bytes.fromhex(case["expected_hex"])


def test_bool_dense_matrix_zeros_invalid_and_padding_bits() -> None:
    cases = json.loads(CORPUS.read_bytes())["cases"]
    case = next(case for case in cases if case["id"] == "bool-dense-padding")
    component = LogicalDenseMatrix(
        name="x",
        logical_type="bool",
        rows=2,
        columns=2,
        values=(True, True, False, True),
        valid=(True, False, True, True),
    )

    assert canonical_bytes((component,)) == bytes.fromhex(case["expected_hex"])


@pytest.mark.parametrize("logical_type", ["float64", "int64", "string", "bool"])
def test_empty_dense_matrices_support_every_logical_type(logical_type: str) -> None:
    component = LogicalDenseMatrix(
        name="empty",
        logical_type=logical_type,  # type: ignore[arg-type]
        rows=0,
        columns=3,
        values=(),
        valid=(),
    )

    encoded = canonical_bytes((component,))

    assert encoded.endswith(bytes.fromhex("00000000000000000300000000000000"))


@pytest.mark.parametrize(
    "component",
    [
        lambda: LogicalDenseMatrix("x", "int64", -1, 1, (), ()),
        lambda: LogicalDenseMatrix("x", "int64", 1, 2, (1,), (True,)),
        lambda: LogicalDenseMatrix("x", "int64", 1, 1, (1,), ()),
    ],
)
def test_dense_model_rejects_inconsistent_shapes(component: object) -> None:
    with pytest.raises(ValueError):
        component()  # type: ignore[operator]


@given(
    st.lists(
        st.tuples(
            st.integers(min_value=-(2**63), max_value=2**63 - 1),
            st.booleans(),
        ),
        max_size=64,
    )
)
def test_int64_vector_encoding_is_container_invariant(
    pairs: list[tuple[int, bool]],
) -> None:
    values = [value for value, _ in pairs]
    valid = [is_valid for _, is_valid in pairs]
    from_lists = LogicalComponent("x", "int64", values, valid)
    from_arrays = LogicalComponent(
        "x",
        "int64",
        np.asarray(values, dtype=">i8"),
        np.asarray(valid, dtype=np.bool_),
    )

    encoded = canonical_bytes((from_lists,))

    assert canonical_bytes((from_arrays,)) == encoded
    assert canonical_sha256((from_lists,)) == hashlib.sha256(encoded).hexdigest()


def test_canonical_stream_rejects_duplicate_or_invalid_utf8_names() -> None:
    first = LogicalComponent("x", "bool", (), ())
    second = LogicalComponent("x", "int64", (), ())

    with pytest.raises(ValueError, match="unique"):
        canonical_bytes((first, second))
    with pytest.raises(ValueError, match="must not be empty"):
        canonical_bytes((LogicalComponent("", "bool", (), ()),))
    with pytest.raises(ValueError, match="UTF-8"):
        canonical_bytes((LogicalComponent("\ud800", "bool", (), ()),))
