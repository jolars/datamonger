from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import (
    EXPECTED_DIGEST,
    FIXTURE,
    LIBSVM_FIXTURE,
    LIBSVM_OPTIONS,
    OPTIONS,
)
from scipy import sparse

from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm
from datamonger.errors import DecodeError


def test_mixed_csv_decodes_to_stable_dataframe_and_golden_digest() -> None:
    decoded = decode_delimited_text(FIXTURE, OPTIONS)

    assert canonical_sha256(decoded.components) == EXPECTED_DIGEST
    assert decoded.data.dtypes.astype(str).tolist() == [
        "Float64",
        "Int64",
        "string",
        "boolean",
    ]
    assert decoded.data.shape == (5, 4)
    assert decoded.data.loc[1, "label"] == "quoted, value"
    assert decoded.data.loc[2, "label"] == 'says "hello"'
    assert pd.isna(decoded.data.loc[2, "measurement"])
    assert pd.isna(decoded.data.loc[1, "count"])
    assert pd.isna(decoded.data.loc[3, "label"])
    assert pd.isna(decoded.data.loc[2, "enabled"])


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("x\n 1\n", "invalid float64"),
        ("x\n+1\n", "invalid float64"),
        ("x\nNaN\n", "invalid float64"),
        ("x\n1e999\n", "finite float64"),
    ],
)
def test_float_grammar_is_strict(tmp_path: Path, body: str, message: str) -> None:
    source = tmp_path / "bad.csv"
    source.write_text(body, encoding="utf-8")
    options = OPTIONS | {"columns": [{"name": "x", "type": "float64"}]}

    with pytest.raises(DecodeError, match=message):
        decode_delimited_text(source, options)


def test_header_and_row_width_are_validated(tmp_path: Path) -> None:
    wrong_header = tmp_path / "header.csv"
    wrong_header.write_text("y\n1\n", encoding="utf-8")
    options = OPTIONS | {"columns": [{"name": "x", "type": "int64"}]}

    with pytest.raises(DecodeError, match="header"):
        decode_delimited_text(wrong_header, options)

    short_row = tmp_path / "row.csv"
    short_row.write_text("x,y\n1\n", encoding="utf-8")
    options = OPTIONS | {
        "columns": [
            {"name": "x", "type": "int64"},
            {"name": "y", "type": "int64"},
        ]
    }
    with pytest.raises(DecodeError, match="fields"):
        decode_delimited_text(short_row, options)


@pytest.mark.parametrize(
    ("logical_type", "raw", "message"),
    [
        ("int64", "+1", "invalid int64"),
        ("int64", "01", "invalid int64"),
        ("int64", str(2**63), "out of range"),
        ("bool", "TRUE", "invalid bool"),
        ("bool", "1", "invalid bool"),
    ],
)
def test_integer_and_boolean_grammars_are_strict(
    tmp_path: Path, logical_type: str, raw: str, message: str
) -> None:
    source = tmp_path / "bad.csv"
    source.write_text(f"x\n{raw}\n", encoding="utf-8")
    options = OPTIONS | {"columns": [{"name": "x", "type": logical_type}]}

    with pytest.raises(DecodeError, match=message):
        decode_delimited_text(source, options)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("x\r1\r", "carriage return"),
        ('x\n"a\nb"\n', "unterminated"),
        ('x\n"ab\n', "unterminated"),
        ('x\nhe"llo\n', "quote inside unquoted"),
        ('x\n"a"b\n', "closing quote"),
    ],
)
def test_record_grammar_is_explicit(tmp_path: Path, body: str, message: str) -> None:
    source = tmp_path / "bad.csv"
    source.write_text(body, encoding="utf-8", newline="")
    options = OPTIONS | {"columns": [{"name": "x", "type": "string"}]}

    with pytest.raises(DecodeError, match=message):
        decode_delimited_text(source, options)


def test_crlf_and_missing_final_terminator_are_supported(tmp_path: Path) -> None:
    source = tmp_path / "crlf.csv"
    source.write_bytes(b"x\r\n1\r\n2")
    options = OPTIONS | {"columns": [{"name": "x", "type": "int64"}]}

    decoded = decode_delimited_text(source, options)

    assert decoded.data["x"].tolist() == [1, 2]


def test_bom_is_rejected_explicitly(tmp_path: Path) -> None:
    source = tmp_path / "bom.csv"
    source.write_bytes(b"\xef\xbb\xbfx\n1\n")
    options = OPTIONS | {"columns": [{"name": "x", "type": "int64"}]}

    with pytest.raises(DecodeError, match="byte-order mark"):
        decode_delimited_text(source, options)


def test_bom_is_rejected_even_for_a_bom_prefixed_column_name(tmp_path: Path) -> None:
    source = tmp_path / "bom.csv"
    source.write_bytes(b"\xef\xbb\xbfx\n1\n")
    options = OPTIONS | {"columns": [{"name": "\ufeffx", "type": "int64"}]}

    with pytest.raises(DecodeError, match="byte-order mark"):
        decode_delimited_text(source, options)


def test_invalid_utf8_is_a_decoding_error(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    source.write_bytes(b"x\n\xff\n")
    options = OPTIONS | {"columns": [{"name": "x", "type": "string"}]}

    with pytest.raises(DecodeError, match="UTF-8"):
        decode_delimited_text(source, options)


def test_libsvm_decodes_to_named_csr_and_response() -> None:
    decoded = decode_libsvm(LIBSVM_FIXTURE, LIBSVM_OPTIONS)

    assert sparse.isspmatrix_csr(decoded.data.features)
    np.testing.assert_array_equal(
        decoded.data.features.toarray(),
        np.array([[1.5, 0.0, 0.0, -2.0], [0.0, 3.0, 0.0, 0.0]]),
    )
    np.testing.assert_array_equal(decoded.data.response, np.array([1, -1]))
    assert decoded.data.response.dtype == np.dtype("int64")
    assert [component.name for component in decoded.components] == [
        "features",
        "response",
    ]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("\ufeff+1 1:1\n", "byte-order mark"),
        ("\n", "blank"),
        ("+1 1:0\n", "zero"),
        ("+1 1:1 1:2\n", "duplicate"),
        ("+1 2:1 1:2\n", "increasing"),
        ("+1 5:1\n", "range"),
        ("+1 0:1\n", "range"),
        ("+1 01:1\n", "feature index"),
        ("+1 1:NaN\n", "feature value"),
        ("label 1:1\n", "label"),
        (" +1 1:1\n", "whitespace"),
    ],
)
def test_libsvm_rejects_malformed_records(
    tmp_path: Path, body: str, message: str
) -> None:
    source = tmp_path / "bad.libsvm"
    source.write_text(body, encoding="utf-8")

    with pytest.raises(DecodeError, match=message):
        decode_libsvm(source, LIBSVM_OPTIONS)


def test_libsvm_float_labels_and_crlf_are_explicitly_supported(tmp_path: Path) -> None:
    source = tmp_path / "float.libsvm"
    source.write_bytes(b"+1.5 1:2\r\n-0.5 4:3")
    options = LIBSVM_OPTIONS | {"label_type": "float64"}

    decoded = decode_libsvm(source, options)

    np.testing.assert_array_equal(decoded.data.response, np.array([1.5, -0.5]))
    assert decoded.data.response.dtype == np.dtype("float64")


def test_libsvm_accepts_trailing_ascii_field_separators(tmp_path: Path) -> None:
    source = tmp_path / "trailing.libsvm"
    source.write_bytes(b"+1 1:2 \t\n")

    decoded = decode_libsvm(source, LIBSVM_OPTIONS)

    np.testing.assert_array_equal(decoded.data.response, np.array([1]))
