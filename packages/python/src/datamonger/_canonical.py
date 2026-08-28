"""Provisional canonical-form version 1 encoder."""

from __future__ import annotations

import hashlib
import io
import math
import struct
from collections.abc import Callable, Iterable
from typing import cast

from datamonger._models import LogicalComponent

_MAGIC = b"DMCF"
_VERSION = 1
_KIND_VECTOR = 1
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


def _write_component(
    component: LogicalComponent, write: Callable[[bytes], object]
) -> None:
    try:
        name = component.name.encode("utf-8")
    except UnicodeEncodeError as error:
        msg = f"component name {component.name!r} is not valid UTF-8"
        raise ValueError(msg) from error
    if not name:
        raise ValueError("component names must not be empty")
    if len(name) > 0xFFFFFFFF:
        raise ValueError("component name exceeds uint32 framing")

    length = len(component.values)
    write(struct.pack("<I", len(name)))
    write(name)
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


def _write_canonical(
    components: Iterable[LogicalComponent], write: Callable[[bytes], object]
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
        _write_component(component, write)


def canonical_bytes(components: Iterable[LogicalComponent]) -> bytes:
    """Return canonical bytes for tests and small diagnostic values."""

    buffer = io.BytesIO()
    _write_canonical(components, cast(Callable[[bytes], object], buffer.write))
    return buffer.getvalue()


def canonical_sha256(components: Iterable[LogicalComponent]) -> str:
    """Hash canonical bytes incrementally without retaining a second copy."""

    digest = hashlib.sha256()
    _write_canonical(components, cast(Callable[[bytes], object], digest.update))
    return digest.hexdigest()
