from __future__ import annotations

import bz2
import gzip
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import (
    CORPUS,
    EXPECTED_DIGEST,
    FIXTURE,
    LIBSVM_DIGEST,
    LIBSVM_FIXTURE,
    LIBSVM_OPTIONS,
    OPTIONS,
)
from scipy import sparse

from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
from datamonger.errors import DecodeError, UnsupportedDecoderError


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
    ("compression", "compress"),
    [("gzip", gzip.compress), ("bzip2", bz2.compress)],
)
def test_delimited_text_decodes_declared_compression(
    tmp_path: Path, compression: str, compress: Callable[[bytes], bytes]
) -> None:
    source = tmp_path / "opaque-artifact"
    source.write_bytes(compress(FIXTURE.read_bytes()))

    decoded = decode_delimited_text(source, OPTIONS, compression=compression)

    assert canonical_sha256(decoded.components) == EXPECTED_DIGEST


@pytest.mark.parametrize(
    ("compression", "compress"),
    [("gzip", gzip.compress), ("bzip2", bz2.compress)],
)
def test_truncated_delimited_compression_is_a_decode_error(
    tmp_path: Path, compression: str, compress: Callable[[bytes], bytes]
) -> None:
    source = tmp_path / "truncated"
    source.write_bytes(compress(FIXTURE.read_bytes())[:-1])

    with pytest.raises(DecodeError, match=compression):
        decode_delimited_text(source, OPTIONS, compression=compression)


def test_delimited_text_rejects_unknown_compression(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.write_bytes(FIXTURE.read_bytes())

    with pytest.raises(UnsupportedDecoderError, match="compression"):
        decode_delimited_text(source, OPTIONS, compression="zip")


def test_missing_tokens_must_be_unique() -> None:
    with pytest.raises(UnsupportedDecoderError, match="unique"):
        decode_delimited_text(FIXTURE, OPTIONS | {"missing_values": ["", ""]})


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
    ("compression", "compress"),
    [("gzip", gzip.compress), ("bzip2", bz2.compress)],
)
def test_libsvm_decodes_declared_compression(
    tmp_path: Path, compression: str, compress: Callable[[bytes], bytes]
) -> None:
    source = tmp_path / "opaque-artifact"
    source.write_bytes(compress(LIBSVM_FIXTURE.read_bytes()))

    decoded = decode_libsvm(source, LIBSVM_OPTIONS, compression=compression)

    assert canonical_sha256(decoded.components) == LIBSVM_DIGEST


@pytest.mark.parametrize(
    ("compression", "compress"),
    [("gzip", gzip.compress), ("bzip2", bz2.compress)],
)
def test_truncated_libsvm_compression_is_a_decode_error(
    tmp_path: Path, compression: str, compress: Callable[[bytes], bytes]
) -> None:
    source = tmp_path / "truncated"
    source.write_bytes(compress(LIBSVM_FIXTURE.read_bytes())[:-1])

    with pytest.raises(DecodeError, match=compression):
        decode_libsvm(source, LIBSVM_OPTIONS, compression=compression)


def test_libsvm_rejects_unknown_compression(tmp_path: Path) -> None:
    source = tmp_path / "artifact"
    source.write_bytes(LIBSVM_FIXTURE.read_bytes())

    with pytest.raises(UnsupportedDecoderError, match="compression"):
        decode_libsvm(source, LIBSVM_OPTIONS, compression="zip")


def test_libsvm_split_preserves_named_outputs_in_normative_order() -> None:
    decoded = decode_libsvm_split(
        LIBSVM_FIXTURE,
        CORPUS / "artifacts" / "small-test.svmlight",
        LIBSVM_OPTIONS,
    )

    assert [component.name for component in decoded.components] == [
        "train_features",
        "train_response",
        "test_features",
        "test_response",
    ]
    np.testing.assert_array_equal(
        decoded.data.train.features.toarray(),
        np.array([[1.5, 0.0, 0.0, -2.0], [0.0, 3.0, 0.0, 0.0]]),
    )
    np.testing.assert_array_equal(
        decoded.data.test.features.toarray(),
        np.array([[2.5, 0.0, -4.0, 0.0], [0.0, 0.001, 0.0, 5.0]]),
    )
    np.testing.assert_array_equal(decoded.data.train.response, np.array([1, -1]))
    np.testing.assert_array_equal(decoded.data.test.response, np.array([0, 2]))
    assert canonical_sha256(decoded.components) == (
        "7169b3668489db5ab1f914ee7f2b102a01d31a55f21ce9b89fc88ce526670ead"
    )


def test_libsvm_split_prefixes_the_declared_target_name() -> None:
    decoded = decode_libsvm_split(
        LIBSVM_FIXTURE,
        CORPUS / "artifacts" / "small-test.svmlight",
        LIBSVM_OPTIONS | {"target_name": "outcome"},
    )

    assert [component.name for component in decoded.components] == [
        "train_features",
        "train_outcome",
        "test_features",
        "test_outcome",
    ]


def test_libsvm_split_parses_each_input_independently(tmp_path: Path) -> None:
    malformed_test = tmp_path / "malformed-test"
    malformed_test.write_text("+1 2:1 1:2\n", encoding="utf-8")

    with pytest.raises(DecodeError, match="increasing"):
        decode_libsvm_split(LIBSVM_FIXTURE, malformed_test, LIBSVM_OPTIONS)


def test_empty_libsvm_artifact_produces_zero_rows(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.write_bytes(b"")

    decoded = decode_libsvm(source, LIBSVM_OPTIONS)

    assert decoded.data.features.shape == (0, 4)
    assert decoded.data.features.nnz == 0
    np.testing.assert_array_equal(decoded.data.response, np.array([], dtype=np.int64))


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({}, "missing decoder options"),
        (LIBSVM_OPTIONS | {"unknown": True}, "unsupported decoder options"),
        (LIBSVM_OPTIONS | {"index_base": 0}, "index_base"),
        (LIBSVM_OPTIONS | {"feature_count": 0}, "positive integer"),
        (LIBSVM_OPTIONS | {"feature_count": True}, "positive integer"),
        (LIBSVM_OPTIONS | {"duplicate_features": "sum"}, "duplicate_features"),
        (LIBSVM_OPTIONS | {"label_type": "string"}, "label_type"),
        (LIBSVM_OPTIONS | {"row_order": "sorted"}, "row_order"),
        (LIBSVM_OPTIONS | {"target_name": ""}, "target_name"),
        (LIBSVM_OPTIONS | {"target_name": "features"}, "target_name"),
    ],
)
def test_libsvm_rejects_incomplete_or_unsupported_recipes(
    options: dict[str, object], message: str
) -> None:
    with pytest.raises(UnsupportedDecoderError, match=message):
        decode_libsvm(LIBSVM_FIXTURE, options)


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
        ("+1 1:1e9999\n", "finite"),
        ("+1 1:-1e-9999\n", "zero"),
        ("+1 1:1 # comment\n", "feature token"),
        ("+1 qid:1 1:1\n", "feature index"),
        ("+1\u00a01:1\n", "label"),
        ("+1 1:1\r", "carriage return"),
        ("9223372036854775808 1:1\n", "out of range"),
        ("+01 1:1\n", "label"),
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


def test_invalid_utf8_is_a_libsvm_decoding_error(tmp_path: Path) -> None:
    source = tmp_path / "bad.libsvm"
    source.write_bytes(b"+1 1:\xff\n")

    with pytest.raises(DecodeError, match="UTF-8"):
        decode_libsvm(source, LIBSVM_OPTIONS)
