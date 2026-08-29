"""Provisional canonical-form version 1 encoder."""

from __future__ import annotations

import hashlib
import io
import struct
from collections.abc import Callable, Iterable
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from datamonger._models import (
    LogicalComponent,
    LogicalDenseMatrix,
    LogicalSparseMatrix,
    LogicalType,
    LogicalValueComponent,
)

_MAGIC = b"DMCF"
_VERSION = 1
_KIND_VECTOR = 1
_KIND_SPARSE_MATRIX = 2
_KIND_DENSE_MATRIX = 3
_TYPE_TAGS = {"float64": 1, "int64": 2, "string": 3, "bool": 4}


def _pack_bitmap(bits: npt.NDArray[np.bool_]) -> bytes:
    return np.packbits(bits, bitorder="little").tobytes()


def _write_name(name_value: str, write: Callable[[bytes], object]) -> None:
    try:
        name = name_value.encode("utf-8")
    except UnicodeEncodeError as error:
        msg = f"component name {name_value!r} is not valid UTF-8"
        raise ValueError(msg) from error
    if not name:
        raise ValueError("component names must not be empty")
    if len(name) > 0xFFFFFFFF:
        raise ValueError("component name exceeds uint32 framing")
    write(struct.pack("<I", len(name)))
    write(name)


def _write_vector(
    component: LogicalComponent, write: Callable[[bytes], object]
) -> None:
    length = len(component.values)
    _write_name(component.name, write)
    write(bytes((_KIND_VECTOR, _TYPE_TAGS[component.logical_type], 1)))
    write(struct.pack("<Q", length))
    write(_pack_bitmap(component.valid))

    _write_values(component.logical_type, component.values, component.valid, write)


def _write_values(
    logical_type: LogicalType,
    values: npt.NDArray[Any] | tuple[str, ...],
    valid: npt.NDArray[np.bool_],
    write: Callable[[bytes], object],
) -> None:
    if logical_type == "float64":
        _write_float64_array(cast(npt.NDArray[np.float64], values), write, valid)
    elif logical_type == "int64":
        _write_int64_array(cast(npt.NDArray[np.int64], values), write, valid)
    elif logical_type == "string":
        for raw, is_valid in zip(values, valid, strict=True):
            try:
                encoded = cast(str, raw).encode("utf-8") if is_valid else b""
            except UnicodeEncodeError as error:
                raise ValueError("logical string is not valid UTF-8") from error
            write(struct.pack("<Q", len(encoded)))
            write(encoded)
    else:
        stored = cast("npt.NDArray[np.bool_]", values) & valid
        write(_pack_bitmap(stored))


def _uint64(value: int, field: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    try:
        return struct.pack("<Q", value)
    except struct.error as error:
        raise ValueError(f"{field} exceeds uint64 framing") from error


def _validate_sparse(component: LogicalSparseMatrix) -> None:
    rows = component.rows
    columns = component.columns
    if rows < 0 or columns < 0:
        raise ValueError("sparse dimensions must be nonnegative")
    _uint64(rows, "row count")
    _uint64(columns, "column count")

    offsets = component.row_offsets
    indices = component.column_indices
    values = component.values
    nonzeros = len(values)
    _uint64(nonzeros, "nonzero count")
    if len(indices) != nonzeros:
        raise ValueError("sparse columns and values must have equal lengths")
    if len(offsets) != rows + 1:
        raise ValueError("sparse row offsets must have rows plus one entries")
    if offsets[0] != 0:
        raise ValueError("sparse row offsets must begin at zero")
    if offsets[-1] != nonzeros:
        raise ValueError("sparse final row offset must equal the nonzero count")
    if bool(np.any(np.diff(offsets) < 0)) or bool(np.any(offsets > nonzeros)):
        raise ValueError("sparse row offsets must be ordered and in range")
    if nonzeros and (bool(np.any(indices < 0)) or bool(np.any(indices >= columns))):
        raise ValueError("sparse column index is out of range")

    # Adjacent indices must increase except across a row boundary; interior
    # offsets mark exactly those boundaries.
    if nonzeros > 1:
        increasing = np.diff(indices) > 0
        starts = offsets[1:-1]
        starts = starts[(starts > 0) & (starts < nonzeros)]
        increasing[starts - 1] = True
        if not bool(increasing.all()):
            raise ValueError("sparse columns must increase within each row")

    if bool(np.any(values == 0.0)):
        raise ValueError("sparse matrices must not store zero values")


# One-mebiword emission chunks keep hashing incremental without a complete
# second copy of a large matrix.
_EMIT_ELEMENTS = 131072


def _write_uint64_array(
    array: npt.NDArray[np.int64], write: Callable[[bytes], object]
) -> None:
    for start in range(0, len(array), _EMIT_ELEMENTS):
        write(array[start : start + _EMIT_ELEMENTS].astype("<u8").tobytes())


def _write_float64_array(
    array: npt.NDArray[np.float64],
    write: Callable[[bytes], object],
    valid: npt.NDArray[np.bool_] | None = None,
) -> None:
    for start in range(0, len(array), _EMIT_ELEMENTS):
        chunk = array[start : start + _EMIT_ELEMENTS].astype("<f8")
        if valid is not None:
            chunk[~valid[start : start + _EMIT_ELEMENTS]] = 0.0
        nans = np.isnan(chunk)
        if bool(nans.any()):
            # Normalize every NaN payload to the canonical quiet NaN.
            chunk[nans] = np.float64("nan")
        # Rewriting the zeros normalizes negative zero to positive zero.
        chunk[chunk == 0.0] = 0.0
        write(chunk.tobytes())


def _write_int64_array(
    array: npt.NDArray[np.int64],
    write: Callable[[bytes], object],
    valid: npt.NDArray[np.bool_],
) -> None:
    for start in range(0, len(array), _EMIT_ELEMENTS):
        chunk = array[start : start + _EMIT_ELEMENTS].astype("<i8")
        chunk[~valid[start : start + _EMIT_ELEMENTS]] = 0
        write(chunk.tobytes())


def _write_sparse_matrix(
    component: LogicalSparseMatrix, write: Callable[[bytes], object]
) -> None:
    _validate_sparse(component)
    _write_name(component.name, write)
    write(bytes((_KIND_SPARSE_MATRIX, _TYPE_TAGS["float64"], 2)))
    write(_uint64(component.rows, "row count"))
    write(_uint64(component.columns, "column count"))
    write(_uint64(len(component.values), "nonzero count"))
    _write_uint64_array(component.row_offsets, write)
    _write_uint64_array(component.column_indices, write)
    _write_float64_array(component.values, write)


def _write_dense_matrix(
    component: LogicalDenseMatrix, write: Callable[[bytes], object]
) -> None:
    _write_name(component.name, write)
    write(bytes((_KIND_DENSE_MATRIX, _TYPE_TAGS[component.logical_type], 2)))
    write(_uint64(component.rows, "dense row count"))
    write(_uint64(component.columns, "dense column count"))
    elements = component.rows * component.columns
    _uint64(elements, "dense element count")
    write(_pack_bitmap(component.valid))
    _write_values(component.logical_type, component.values, component.valid, write)


def _write_canonical(
    components: Iterable[LogicalValueComponent], write: Callable[[bytes], object]
) -> None:
    materialized = tuple(components)
    if len(materialized) > 0xFFFFFFFF:
        raise ValueError("component count exceeds uint32 framing")
    names = [component.name for component in materialized]
    if len(names) != len(set(names)):
        raise ValueError("canonical component names must be unique")

    write(_MAGIC)
    write(struct.pack("<H", _VERSION))
    write(struct.pack("<I", len(materialized)))
    for component in materialized:
        if isinstance(component, LogicalSparseMatrix):
            _write_sparse_matrix(component, write)
        elif isinstance(component, LogicalDenseMatrix):
            _write_dense_matrix(component, write)
        else:
            _write_vector(component, write)


def canonical_bytes(components: Iterable[LogicalValueComponent]) -> bytes:
    """Return canonical bytes for tests and small diagnostic values."""

    buffer = io.BytesIO()
    _write_canonical(components, cast(Callable[[bytes], object], buffer.write))
    return buffer.getvalue()


def canonical_sha256(components: Iterable[LogicalValueComponent]) -> str:
    """Hash canonical bytes incrementally without retaining a second copy."""

    digest = hashlib.sha256()
    _write_canonical(components, cast(Callable[[bytes], object], digest.update))
    return digest.hexdigest()
