from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger.errors import DecodeError

FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"
EXPECTED_DIGEST = "e25d27e8b0008332d778cd48429a7c4f7af59411884092e52f120da63f26e726"
OPTIONS = {
    "encoding": "utf-8",
    "delimiter": ",",
    "header": True,
    "quote": '"',
    "escape": "double",
    "missing_values": [""],
    "row_order": "source",
    "columns": [
        {"name": "measurement", "type": "float64"},
        {"name": "count", "type": "int64"},
        {"name": "label", "type": "string"},
        {"name": "enabled", "type": "bool"},
    ],
}


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


def test_invalid_utf8_is_a_decoding_error(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    source.write_bytes(b"x\n\xff\n")
    options = OPTIONS | {"columns": [{"name": "x", "type": "string"}]}

    with pytest.raises(DecodeError, match="UTF-8"):
        decode_delimited_text(source, options)
