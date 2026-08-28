"""Shared public and internal value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from typing import Literal, TypeAlias

import pandas as pd

LogicalType: TypeAlias = Literal["float64", "int64", "string", "bool"]
VerificationLevel: TypeAlias = Literal["artifact", "decoded"]
Pathish: TypeAlias = str | PathLike[str]


@dataclass(frozen=True)
class Registry:
    """Location and strong selector for one immutable registry index."""

    release: str
    index_sha256: str
    index_url: str


@dataclass(frozen=True)
class FetchInfo:
    """Reproducibility metadata for a completed fetch."""

    dataset_id: str
    registry_release: str
    registry_index_sha256: str
    artifact_digests: Mapping[str, str]
    verification: VerificationLevel
    canonical_form: int | None
    canonical_digest: str | None


@dataclass(frozen=True)
class FetchResult:
    """Decoded data together with its reproducibility metadata."""

    data: pd.DataFrame
    info: FetchInfo


@dataclass(frozen=True)
class LogicalComponent:
    """One ordered logical vector with missingness kept separate from values."""

    name: str
    logical_type: LogicalType
    values: tuple[object, ...]
    valid: tuple[bool, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(self.valid):
            msg = "logical component values and validity must have equal lengths"
            raise ValueError(msg)


@dataclass(frozen=True)
class DecodedTable:
    """A native table and the logical components from which it was built."""

    data: pd.DataFrame
    components: tuple[LogicalComponent, ...]
