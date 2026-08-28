"""Provisional canonical-form version 1 encoder."""

from __future__ import annotations

import hashlib
import io
import math
import struct
from collections.abc import Callable, Iterable
from typing import cast

from datamonger._models import (
    LogicalComponent,
    LogicalSparseMatrix,
    LogicalValueComponent,
)

_MAGIC = b"DMCF"
_VERSION = 1
_KIND_VECTOR = 1
_KIND_SPARSE_MATRIX = 2
_TYPE_TAGS = {"float64": 1, "int64": 2, "string": 3, "bool": 4}
_CANONICAL_NAN = 0x7FF8000000000000


def _pack_bitmap(bits: Iterable[bool], length: int) -> bytes:
    packed = bytearray((length + 7) // 8)
    for index, value in enumerate(bits):
        if value:
            packed[index // 8] |= 1 << (index % 8)
    return bytes(packed)


def _float_bits(value: float, valid: bool) -> int:
    if not valid or value == 0.0:
        return 0
    if math.isnan(value):
        return _CANONICAL_NAN
    return cast(int, struct.unpack("<Q", struct.pack("<d", value))[0])


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
    write(_pack_bitmap(component.valid, length))

    if component.logical_type == "float64":
        for raw, valid in zip(component.values, component.valid, strict=True):
            if not isinstance(raw, float):
                raise TypeError("float64 logical values must be Python floats")
            write(struct.pack("<Q", _float_bits(raw, valid)))
        return

    if component.logical_type == "int64":
        for raw, valid in zip(component.values, component.valid, strict=True):
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise TypeError("int64 logical values must be Python integers")
            integer = raw if valid else 0
            try:
                write(struct.pack("<q", integer))
            except struct.error as error:
                raise ValueError("int64 logical value is out of range") from error
        return

    if component.logical_type == "string":
        for raw, valid in zip(component.values, component.valid, strict=True):
            if not isinstance(raw, str):
                raise TypeError("string logical values must be Python strings")
            try:
                encoded = raw.encode("utf-8") if valid else b""
            except UnicodeEncodeError as error:
                raise ValueError("logical string is not valid UTF-8") from error
            write(struct.pack("<Q", len(encoded)))
            write(encoded)
        return

    bool_values = []
    for raw, valid in zip(component.values, component.valid, strict=True):
        if not isinstance(raw, bool):
            raise TypeError("bool logical values must be Python booleans")
        bool_values.append(valid and raw)
    write(_pack_bitmap(bool_values, length))


def _uint64(value: int, field: str) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"sparse {field} must be an integer")
    try:
        return struct.pack("<Q", value)
    except struct.error as error:
        raise ValueError(f"sparse {field} exceeds uint64 framing") from error


def _validate_sparse(component: LogicalSparseMatrix) -> None:
    rows = component.rows
    columns = component.columns
    if rows < 0 or columns < 0:
        raise ValueError("sparse dimensions must be nonnegative")
    _uint64(rows, "row count")
    _uint64(columns, "column count")

    nonzeros = len(component.values)
    _uint64(nonzeros, "nonzero count")
    if len(component.column_indices) != nonzeros:
        raise ValueError("sparse columns and values must have equal lengths")
    if len(component.row_offsets) != rows + 1:
        raise ValueError("sparse row offsets must have rows plus one entries")
    if not component.row_offsets or component.row_offsets[0] != 0:
        raise ValueError("sparse row offsets must begin at zero")
    if component.row_offsets[-1] != nonzeros:
        raise ValueError("sparse final row offset must equal the nonzero count")

    previous_offset = 0
    for offset in component.row_offsets:
        _uint64(offset, "row offset")
        if offset < previous_offset or offset > nonzeros:
            raise ValueError("sparse row offsets must be ordered and in range")
        previous_offset = offset

    for row in range(rows):
        previous_column = -1
        start = component.row_offsets[row]
        stop = component.row_offsets[row + 1]
        for position in range(start, stop):
            column = component.column_indices[position]
            _uint64(column, "column index")
            if column >= columns:
                raise ValueError("sparse column index is out of range")
            if column <= previous_column:
                raise ValueError("sparse columns must increase within each row")
            previous_column = column

            value = component.values[position]
            if not isinstance(value, float):
                raise TypeError("float64 sparse values must be Python floats")
            if value == 0.0:
                raise ValueError("sparse matrices must not store zero values")


def _write_sparse_matrix(
    component: LogicalSparseMatrix, write: Callable[[bytes], object]
) -> None:
    _validate_sparse(component)
    _write_name(component.name, write)
    write(bytes((_KIND_SPARSE_MATRIX, _TYPE_TAGS["float64"], 2)))
    write(_uint64(component.rows, "row count"))
    write(_uint64(component.columns, "column count"))
    write(_uint64(len(component.values), "nonzero count"))
    for offset in component.row_offsets:
        write(_uint64(offset, "row offset"))
    for column in component.column_indices:
        write(_uint64(column, "column index"))
    for value in component.values:
        write(struct.pack("<Q", _float_bits(value, True)))


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
