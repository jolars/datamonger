"""Validate Python representation recipes before passing them to the core."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, cast

from datamonger._errors import UnsupportedDecoderError
from datamonger._models import LogicalType
from datamonger._validate import require_array

LabelType = Literal["float64", "int64"]

_QUOTE = '"'
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


def delimited_options(
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


_MAX_EXACT_JSON_INTEGER = 2**53 - 1
_LIBSVM_OPTIONS = {
    "index_base",
    "feature_count",
    "duplicate_features",
    "label_type",
    "row_order",
    "target_name",
}


def libsvm_options(
    options: Mapping[str, object],
) -> tuple[int, LabelType, str]:
    unknown = set(options) - _LIBSVM_OPTIONS
    if unknown:
        raise UnsupportedDecoderError(f"unsupported decoder options: {sorted(unknown)}")
    missing = _LIBSVM_OPTIONS - set(options)
    if missing:
        raise UnsupportedDecoderError(f"missing decoder options: {sorted(missing)}")

    expected = {
        "index_base": 1,
        "duplicate_features": "error",
        "row_order": "source",
    }
    for key, value in expected.items():
        if options[key] != value:
            raise UnsupportedDecoderError(f"unsupported {key}: {options[key]!r}")

    feature_count = options["feature_count"]
    if (
        isinstance(feature_count, bool)
        or not isinstance(feature_count, int)
        or feature_count <= 0
        or feature_count > _MAX_EXACT_JSON_INTEGER
    ):
        raise UnsupportedDecoderError(
            "feature_count must be a positive integer in the exact JSON range"
        )

    label_type = options["label_type"]
    if label_type not in {"float64", "int64"}:
        raise UnsupportedDecoderError(f"unsupported label_type: {label_type!r}")

    target_name = options["target_name"]
    if not isinstance(target_name, str) or not target_name or target_name == "features":
        raise UnsupportedDecoderError(
            "target_name must be nonempty and distinct from 'features'"
        )
    return feature_count, label_type, target_name
