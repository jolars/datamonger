"""Shared JSON-shape validators parameterized by error type."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

ErrorFactory = Callable[[str], Exception]


def require_mapping(
    value: object, field: str, error: ErrorFactory
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise error(f"{field} must be an object")
    return cast(Mapping[str, Any], value)


def require_array(value: object, field: str, error: ErrorFactory) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise error(f"{field} must be an array")
    return value


def require_string(value: object, field: str, error: ErrorFactory) -> str:
    if not isinstance(value, str):
        raise error(f"{field} must be a string")
    return value


def require_integer(value: object, field: str, error: ErrorFactory) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error(f"{field} must be an integer")
    return value
