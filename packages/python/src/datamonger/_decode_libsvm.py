"""Explicit provisional LIBSVM version 1 decoding."""

from __future__ import annotations

import math
import re
from array import array
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

import numpy as np
from scipy import sparse

from datamonger._errors import DecodeError, UnsupportedDecoderError
from datamonger._models import (
    DecodedSparseDataset,
    LogicalComponent,
    LogicalSparseMatrix,
    LogicalType,
    Pathish,
    ResponseArray,
    SparseDataset,
)

LabelType = Literal["float64", "int64"]

_INTEGER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)\Z")
_INDEX = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_FLOAT = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_FIELDS = re.compile(r"[ \t]+")
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1
_SUPPORTED_OPTIONS = {
    "index_base",
    "feature_count",
    "duplicate_features",
    "label_type",
    "row_order",
    "target_name",
}


def _validate_options(
    options: Mapping[str, object],
) -> tuple[int, LabelType, str]:
    unknown = set(options) - _SUPPORTED_OPTIONS
    if unknown:
        raise UnsupportedDecoderError(f"unsupported decoder options: {sorted(unknown)}")
    missing = _SUPPORTED_OPTIONS - set(options)
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
    ):
        raise UnsupportedDecoderError("feature_count must be a positive integer")

    label_type = options["label_type"]
    if label_type not in {"float64", "int64"}:
        raise UnsupportedDecoderError(f"unsupported label_type: {label_type!r}")

    target_name = options["target_name"]
    if not isinstance(target_name, str) or not target_name or target_name == "features":
        raise UnsupportedDecoderError(
            "target_name must be nonempty and distinct from 'features'"
        )
    return feature_count, label_type, target_name


def _parse_int64(raw: str, line_number: int) -> int:
    if _INTEGER.fullmatch(raw) is None:
        raise DecodeError(f"invalid int64 label at line {line_number}: {raw!r}")
    value = int(raw)
    if not _INT64_MIN <= value <= _INT64_MAX:
        raise DecodeError(f"int64 label out of range at line {line_number}: {raw!r}")
    return value


def _parse_float(raw: str, line_number: int, field: str) -> float:
    if _FLOAT.fullmatch(raw) is None:
        raise DecodeError(f"invalid {field} at line {line_number}: {raw!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise DecodeError(f"expected finite {field} at line {line_number}: {raw!r}")
    return value


def _record_body(raw_line: str, line_number: int) -> str:
    if raw_line.endswith("\r\n"):
        body = raw_line[:-2]
    elif raw_line.endswith("\n"):
        body = raw_line[:-1]
    elif raw_line.endswith("\r"):
        raise DecodeError(f"unsupported bare carriage return at line {line_number}")
    else:
        body = raw_line

    if not body:
        raise DecodeError(f"blank LIBSVM record at line {line_number}")
    if line_number == 1 and body.startswith("\ufeff"):
        raise DecodeError("LIBSVM artifact contains a byte-order mark")
    if body[0] in " \t":
        raise DecodeError(f"leading whitespace at line {line_number}")
    return body.rstrip(" \t")


def decode_libsvm(path: Pathish, options: Mapping[str, object]) -> DecodedSparseDataset:
    """Decode the strict provisional LIBSVM version 1 representation."""

    feature_count, label_type, target_name = _validate_options(options)
    labels: list[int | float] = []
    # Unboxed accumulators keep decode-time memory near the size of the
    # resulting arrays instead of a boxed object per stored value.
    row_offsets = array("q", (0,))
    column_indices = array("q")
    feature_values = array("d")

    try:
        with Path(path).open(
            "r", encoding="utf-8", errors="strict", newline=""
        ) as source:
            for line_number, raw_line in enumerate(source, start=1):
                body = _record_body(raw_line, line_number)
                fields = _FIELDS.split(body)
                raw_label = fields[0]
                label = (
                    _parse_int64(raw_label, line_number)
                    if label_type == "int64"
                    else _parse_float(raw_label, line_number, "float64 label")
                )
                labels.append(label)

                previous_index = 0
                for token in fields[1:]:
                    if token.count(":") != 1:
                        raise DecodeError(
                            f"invalid feature token at line {line_number}: {token!r}"
                        )
                    raw_index, raw_value = token.split(":", maxsplit=1)
                    if _INDEX.fullmatch(raw_index) is None:
                        raise DecodeError(
                            f"invalid feature index at line {line_number}: "
                            f"{raw_index!r}"
                        )
                    source_index = int(raw_index)
                    if source_index == previous_index:
                        raise DecodeError(
                            f"duplicate feature index at line {line_number}: "
                            f"{source_index}"
                        )
                    if source_index < previous_index:
                        raise DecodeError(
                            f"feature indices must be increasing at line {line_number}"
                        )
                    if not 1 <= source_index <= feature_count:
                        raise DecodeError(
                            f"feature index out of range at line {line_number}: "
                            f"{source_index}"
                        )
                    value = _parse_float(raw_value, line_number, "feature value")
                    if value == 0.0:
                        raise DecodeError(
                            f"stored zero feature value at line {line_number}: "
                            f"{token!r}"
                        )
                    previous_index = source_index
                    column_indices.append(source_index - 1)
                    feature_values.append(value)
                row_offsets.append(len(feature_values))
    except UnicodeDecodeError as error:
        raise DecodeError("LIBSVM artifact is not valid UTF-8") from error
    except OSError as error:
        raise DecodeError(f"cannot read LIBSVM artifact: {error}") from error

    response: ResponseArray
    if label_type == "int64":
        response = np.asarray(cast(list[int], labels), dtype=np.int64)
    else:
        response = np.asarray(cast(list[float], labels), dtype=np.float64)
    # The CSR arrays double as the logical component, so no second complete
    # copy of the matrix is materialized for canonical hashing.
    offsets_array = np.frombuffer(row_offsets, dtype=np.int64)
    indices_array = np.frombuffer(column_indices, dtype=np.int64)
    values_array = np.frombuffer(feature_values, dtype=np.float64)
    features = sparse.csr_matrix(
        (values_array, indices_array, offsets_array),
        shape=(len(labels), feature_count),
    )
    matrix = LogicalSparseMatrix(
        name="features",
        rows=len(labels),
        columns=feature_count,
        row_offsets=offsets_array,
        column_indices=indices_array,
        values=values_array,
    )
    response_component = LogicalComponent(
        name=target_name,
        logical_type=cast(LogicalType, label_type),
        values=tuple(labels),
        valid=(True,) * len(labels),
    )
    return DecodedSparseDataset(
        data=SparseDataset(features=features, response=response),
        components=(matrix, response_component),
    )
