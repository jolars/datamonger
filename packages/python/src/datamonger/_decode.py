"""Delimited-text version 1 decoding."""

from __future__ import annotations

import bz2
import gzip
import math
import re
from array import array
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO, cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from datamonger._errors import DecodeError, UnsupportedDecoderError
from datamonger._models import DecodedTable, LogicalComponent, LogicalType, Pathish
from datamonger._validate import require_array

_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_FLOAT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_QUOTE = '"'
_SUPPORTED_COMPRESSIONS = {"none", "gzip", "bzip2"}
_SUPPORTED_DELIMITERS = {",", "\t"}
_SUPPORTED_OPTIONS = {
    "encoding",
    "delimiter",
    "header",
    "quote",
    "escape",
    "missing_values",
    "row_order",
    "columns",
}


def _require_sequence(value: object, field: str) -> Sequence[object]:
    return require_array(value, field, UnsupportedDecoderError)


def _parse_columns(
    options: Mapping[str, object],
) -> tuple[tuple[str, LogicalType], ...]:
    raw_columns = _require_sequence(options.get("columns"), "columns")
    columns: list[tuple[str, LogicalType]] = []
    for raw in raw_columns:
        if not isinstance(raw, Mapping):
            raise UnsupportedDecoderError("each column must be an object")
        name = raw.get("name")
        logical_type = raw.get("type")
        if (
            not isinstance(name, str)
            or not name
            or logical_type
            not in {
                "float64",
                "int64",
                "string",
                "bool",
            }
        ):
            raise UnsupportedDecoderError("column name or logical type is invalid")
        columns.append((name, cast(LogicalType, logical_type)))
    if not columns or len({name for name, _ in columns}) != len(columns):
        raise UnsupportedDecoderError("column names must be nonempty and unique")
    return tuple(columns)


def _validate_options(
    options: Mapping[str, object],
) -> tuple[tuple[tuple[str, LogicalType], ...], frozenset[str], str]:
    unknown = set(options) - _SUPPORTED_OPTIONS
    if unknown:
        raise UnsupportedDecoderError(f"unsupported decoder options: {sorted(unknown)}")
    required = _SUPPORTED_OPTIONS - {"missing_values"}
    missing = required - set(options)
    if missing:
        raise UnsupportedDecoderError(f"missing decoder options: {sorted(missing)}")
    expected = {
        "encoding": "utf-8",
        "quote": _QUOTE,
        "escape": "double",
        "row_order": "source",
    }
    for key, value in expected.items():
        if options[key] != value:
            raise UnsupportedDecoderError(f"unsupported {key}: {options[key]!r}")
    if options["header"] is not True:
        raise UnsupportedDecoderError(f"unsupported header: {options['header']!r}")
    delimiter = options["delimiter"]
    if not isinstance(delimiter, str) or delimiter not in _SUPPORTED_DELIMITERS:
        raise UnsupportedDecoderError(f"unsupported delimiter: {delimiter!r}")

    missing_values = _require_sequence(
        options.get("missing_values", []), "missing_values"
    )
    if not all(isinstance(value, str) for value in missing_values):
        raise UnsupportedDecoderError("missing values must be strings")
    typed_missing_values = cast(Sequence[str], missing_values)
    if len(set(typed_missing_values)) != len(typed_missing_values):
        raise UnsupportedDecoderError("missing values must be unique")
    return (
        _parse_columns(options),
        frozenset(typed_missing_values),
        delimiter,
    )


def _parse_value(raw: str, logical_type: LogicalType, row: int, column: str) -> object:
    if logical_type == "string":
        return raw
    if logical_type == "bool":
        if raw == "true":
            return True
        if raw == "false":
            return False
        raise DecodeError(f"invalid bool at row {row}, column {column!r}: {raw!r}")
    if logical_type == "int64":
        if _INTEGER.fullmatch(raw) is None:
            raise DecodeError(f"invalid int64 at row {row}, column {column!r}: {raw!r}")
        integer = int(raw)
        if not _INT64_MIN <= integer <= _INT64_MAX:
            raise DecodeError(
                f"int64 out of range at row {row}, column {column!r}: {raw!r}"
            )
        return integer
    if _FLOAT.fullmatch(raw) is None:
        raise DecodeError(f"invalid float64 at row {row}, column {column!r}: {raw!r}")
    floating = float(raw)
    if not math.isfinite(floating):
        raise DecodeError(
            f"expected finite float64 at row {row}, column {column!r}: {raw!r}"
        )
    return floating


def _record_body(raw_line: str, line_number: int) -> str:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2]
    if raw_line.endswith("\n"):
        return raw_line[:-1]
    if raw_line.endswith("\r"):
        raise DecodeError(f"unsupported bare carriage return at line {line_number}")
    return raw_line


def _parse_record(body: str, line_number: int, delimiter: str) -> list[str]:
    """Split one record into fields under the version 1 grammar."""

    fields: list[str] = []
    position = 0
    length = len(body)
    while True:
        if position < length and body[position] == _QUOTE:
            position += 1
            characters: list[str] = []
            while True:
                if position >= length:
                    raise DecodeError(
                        f"unterminated quoted field at line {line_number}"
                    )
                character = body[position]
                if character == _QUOTE:
                    if position + 1 < length and body[position + 1] == _QUOTE:
                        characters.append(_QUOTE)
                        position += 2
                    else:
                        position += 1
                        break
                else:
                    characters.append(character)
                    position += 1
            fields.append("".join(characters))
            if position == length:
                return fields
            if body[position] != delimiter:
                raise DecodeError(
                    f"invalid character after closing quote at line {line_number}"
                )
        else:
            start = position
            while position < length and body[position] not in (delimiter, _QUOTE):
                position += 1
            if position < length and body[position] == _QUOTE:
                raise DecodeError(f"quote inside unquoted field at line {line_number}")
            fields.append(body[start:position])
            if position == length:
                return fields
        position += 1


def _missing_placeholder(logical_type: LogicalType) -> object:
    if logical_type == "float64":
        return 0.0
    if logical_type == "int64":
        return 0
    if logical_type == "string":
        return ""
    return False


def _accumulator(logical_type: LogicalType) -> array[Any] | list[object]:
    # Numeric columns store values unboxed as they parse; boolean columns are
    # packed into bytes, and only strings stay Python objects.
    if logical_type == "float64":
        return array("d")
    if logical_type == "int64":
        return array("q")
    if logical_type == "bool":
        return array("b")
    return []


def _component_values(
    logical_type: LogicalType, accumulated: array[Any] | list[object]
) -> npt.NDArray[Any] | tuple[str, ...]:
    if logical_type == "string":
        return tuple(cast("list[str]", accumulated))
    values_array = cast("array[Any]", accumulated)
    typed = np.frombuffer(values_array, dtype=values_array.typecode)
    if logical_type == "bool":
        return typed.astype(np.bool_)
    return typed


def _make_dataframe(components: tuple[LogicalComponent, ...]) -> pd.DataFrame:
    series: dict[str, pd.Series[Any]] = {}
    for component in components:
        mask = ~component.valid
        data: Any
        if component.logical_type == "string":
            native: list[Any] = [
                value if valid else pd.NA
                for value, valid in zip(component.values, component.valid, strict=True)
            ]
            data = pd.array(native, dtype=cast(Any, "string"))
        else:
            # The masked-array constructors take the unboxed values directly;
            # copies keep the frame independent of the logical components.
            typed = cast("npt.NDArray[Any]", component.values)
            if component.logical_type == "float64":
                data = pd.arrays.FloatingArray(typed.copy(), mask.copy())
            elif component.logical_type == "int64":
                data = pd.arrays.IntegerArray(typed.copy(), mask.copy())
            else:
                data = pd.arrays.BooleanArray(typed.copy(), mask.copy())
        series[component.name] = pd.Series(data)
    return pd.DataFrame(series)


def _open_text(path: Pathish, compression: str) -> TextIO:
    if compression not in _SUPPORTED_COMPRESSIONS:
        raise UnsupportedDecoderError(f"unsupported compression: {compression!r}")
    if compression == "gzip":
        return gzip.open(path, mode="rt", encoding="utf-8", errors="strict", newline="")
    if compression == "bzip2":
        return bz2.open(path, mode="rt", encoding="utf-8", errors="strict", newline="")
    return Path(path).open("r", encoding="utf-8", errors="strict", newline="")


def decode_delimited_text(
    path: Pathish,
    options: Mapping[str, object],
    *,
    compression: str = "none",
) -> DecodedTable:
    """Decode a delimited-text version 1 representation."""

    columns, missing_values, delimiter = _validate_options(options)
    values = [_accumulator(logical_type) for _, logical_type in columns]
    validity = [bytearray() for _ in columns]

    try:
        with _open_text(path, compression) as source:
            header: list[str] | None = None
            for row_number, raw_line in enumerate(source, start=1):
                if row_number == 1:
                    if raw_line.startswith("\ufeff"):
                        raise DecodeError(
                            "delimited-text artifact contains a byte-order mark"
                        )
                    header = _parse_record(_record_body(raw_line, 1), 1, delimiter)
                    expected_header = [name for name, _ in columns]
                    if header != expected_header:
                        raise DecodeError(
                            f"header {header!r} does not match {expected_header!r}"
                        )
                    continue
                body = _record_body(raw_line, row_number)
                row = _parse_record(body, row_number, delimiter)
                if len(row) != len(columns):
                    message = (
                        f"row {row_number} has {len(row)} fields; "
                        f"expected {len(columns)}"
                    )
                    raise DecodeError(message)
                for index, ((name, logical_type), raw) in enumerate(
                    zip(columns, row, strict=True)
                ):
                    valid = raw not in missing_values
                    value = (
                        _parse_value(raw, logical_type, row_number, name)
                        if valid
                        else _missing_placeholder(logical_type)
                    )
                    values[index].append(value)
                    validity[index].append(valid)
            if header is None:
                raise DecodeError("delimited-text artifact has no header")
    except UnicodeDecodeError as error:
        raise DecodeError("delimited-text artifact is not valid UTF-8") from error
    except EOFError as error:
        raise DecodeError(
            f"cannot decompress {compression} delimited-text artifact: {error}"
        ) from error
    except OSError as error:
        operation = "read" if compression == "none" else f"decompress {compression}"
        raise DecodeError(
            f"cannot {operation} delimited-text artifact: {error}"
        ) from error

    components = tuple(
        LogicalComponent(
            name=name,
            logical_type=logical_type,
            values=_component_values(logical_type, component_values),
            valid=np.frombuffer(component_validity, dtype=np.bool_),
        )
        for (name, logical_type), component_values, component_validity in zip(
            columns, values, validity, strict=True
        )
    )
    return DecodedTable(data=_make_dataframe(components), components=components)
