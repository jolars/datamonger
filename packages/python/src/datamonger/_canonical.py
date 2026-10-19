"""Canonical-form version 1 encoding through datamonger-core."""

from __future__ import annotations

from collections.abc import Iterable

from datamonger import _native
from datamonger._models import LogicalValueComponent


def canonical_bytes(components: Iterable[LogicalValueComponent]) -> bytes:
    """Return canonical bytes for tests and small diagnostic values."""

    return _native.canonical_bytes(tuple(components))


def canonical_sha256(components: Iterable[LogicalValueComponent]) -> str:
    """Hash canonical bytes incrementally without retaining the stream."""

    return _native.canonical_sha256(tuple(components))
