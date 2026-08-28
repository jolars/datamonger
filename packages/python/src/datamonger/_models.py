"""Shared public and internal value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from typing import Literal, TypeAlias

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import sparse

LogicalType: TypeAlias = Literal["float64", "int64", "string", "bool"]
VerificationLevel: TypeAlias = Literal["artifact", "decoded"]
Pathish: TypeAlias = str | PathLike[str]
ResponseArray: TypeAlias = npt.NDArray[np.int64] | npt.NDArray[np.float64]


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
class SparseDataset:
    """A named sparse feature matrix and its response vector."""

    features: sparse.csr_matrix
    response: ResponseArray


DatasetData: TypeAlias = pd.DataFrame | SparseDataset


@dataclass(frozen=True)
class FetchResult:
    """Decoded data together with its reproducibility metadata."""

    data: DatasetData
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
class LogicalSparseMatrix:
    """One logical float64 sparse matrix in canonical CSR order."""

    name: str
    rows: int
    columns: int
    row_offsets: tuple[int, ...]
    column_indices: tuple[int, ...]
    values: tuple[float, ...]

    @property
    def logical_type(self) -> Literal["float64"]:
        """Return the sole sparse element type in canonical-form version 1."""

        return "float64"


LogicalValueComponent: TypeAlias = LogicalComponent | LogicalSparseMatrix


@dataclass(frozen=True)
class DecodedTable:
    """A native table and the logical components from which it was built."""

    data: pd.DataFrame
    components: tuple[LogicalComponent, ...]


@dataclass(frozen=True)
class DecodedSparseDataset:
    """A native sparse dataset and its ordered logical components."""

    data: SparseDataset
    components: tuple[LogicalSparseMatrix, LogicalComponent]
