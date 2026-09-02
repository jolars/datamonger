"""Shared public and internal value objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar, cast

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import sparse

LogicalType: TypeAlias = Literal["float64", "int64", "string", "bool"]
VerificationLevel: TypeAlias = Literal["artifact", "decoded"]
CacheEntryKind: TypeAlias = Literal["artifact", "registry"]
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


@dataclass(frozen=True)
class SparseDatasetSplit:
    """Separate training and test sparse datasets from one representation."""

    train: SparseDataset
    test: SparseDataset


DatasetData: TypeAlias = pd.DataFrame | SparseDataset | SparseDatasetSplit


@dataclass(frozen=True)
class FetchResult:
    """Decoded data together with its reproducibility metadata."""

    data: DatasetData
    info: FetchInfo


@dataclass(frozen=True)
class CacheEntry:
    """One content-addressed object found in the Python client cache."""

    kind: CacheEntryKind
    sha256: str
    size: int
    modified_at: datetime
    path: Path
    valid: bool
    datasets: tuple[str, ...]
    registry_release: str | None


@dataclass(frozen=True)
class CacheInfo:
    """A point-in-time inventory of the Python client cache."""

    location: Path
    total_size: int
    entries: tuple[CacheEntry, ...]


@dataclass(frozen=True)
class CacheCleanResult:
    """The entries removed or skipped by one manual cache eviction."""

    location: Path
    removed: tuple[CacheEntry, ...]
    skipped: tuple[CacheEntry, ...]

    @property
    def bytes_removed(self) -> int:
        """Return the number of cached bytes removed."""

        return sum(entry.size for entry in self.removed)


_Scalar = TypeVar("_Scalar", np.int64, np.float64, np.bool_)


def _typed_array(
    value: object, dtype: type[_Scalar], field: str
) -> npt.NDArray[_Scalar]:
    array = np.asarray(value)
    if array.ndim != 1:
        raise ValueError(f"{field} must be one-dimensional")
    if array.dtype == dtype:
        return cast(npt.NDArray[_Scalar], array)
    if array.size == 0:
        return np.zeros(0, dtype=dtype)
    try:
        return array.astype(dtype, casting="safe")
    except TypeError as error:
        raise TypeError(f"{field} must have {dtype.__name__} values") from error


_VECTOR_DTYPES: Mapping[str, type[np.float64] | type[np.int64] | type[np.bool_]] = {
    "float64": np.float64,
    "int64": np.int64,
    "bool": np.bool_,
}


@dataclass(frozen=True)
class LogicalComponent:
    """One ordered logical vector with missingness kept separate from values.

    Numeric and boolean values are stored unboxed so the canonical hash can
    be fed from them directly; strings stay a tuple of Python strings.
    """

    name: str
    logical_type: LogicalType
    values: npt.NDArray[Any] | tuple[str, ...]
    valid: npt.NDArray[np.bool_]

    def __post_init__(self) -> None:
        field = f"{self.logical_type} logical values"
        if self.logical_type == "string":
            values: npt.NDArray[Any] | tuple[str, ...] = tuple(
                cast(Sequence[str], self.values)
            )
            if not all(isinstance(value, str) for value in values):
                raise TypeError(f"{field} must be Python strings")
        else:
            values = _typed_array(self.values, _VECTOR_DTYPES[self.logical_type], field)
        object.__setattr__(self, "values", values)
        object.__setattr__(
            self, "valid", _typed_array(self.valid, np.bool_, "validity mask")
        )
        if len(values) != len(self.valid):
            msg = "logical component values and validity must have equal lengths"
            raise ValueError(msg)


@dataclass(frozen=True)
class LogicalSparseMatrix:
    """One logical float64 sparse matrix in canonical CSR order.

    The arrays are stored unboxed so the canonical hash can be fed from them
    directly instead of from a second, boxed copy of every value.
    """

    name: str
    rows: int
    columns: int
    row_offsets: npt.NDArray[np.int64]
    column_indices: npt.NDArray[np.int64]
    values: npt.NDArray[np.float64]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "row_offsets", _typed_array(self.row_offsets, np.int64, "row offsets")
        )
        object.__setattr__(
            self,
            "column_indices",
            _typed_array(self.column_indices, np.int64, "column indices"),
        )
        object.__setattr__(
            self, "values", _typed_array(self.values, np.float64, "values")
        )

    @property
    def logical_type(self) -> Literal["float64"]:
        """Return the sole sparse element type in canonical-form version 1."""

        return "float64"


@dataclass(frozen=True)
class LogicalDenseMatrix:
    """One row-major logical dense matrix with explicit missingness."""

    name: str
    logical_type: LogicalType
    rows: int
    columns: int
    values: npt.NDArray[Any] | tuple[str, ...]
    valid: npt.NDArray[np.bool_]

    def __post_init__(self) -> None:
        if (
            isinstance(self.rows, bool)
            or not isinstance(self.rows, int)
            or isinstance(self.columns, bool)
            or not isinstance(self.columns, int)
            or self.rows < 0
            or self.columns < 0
        ):
            raise ValueError("dense dimensions must be nonnegative integers")
        field = f"{self.logical_type} dense values"
        if self.logical_type == "string":
            values: npt.NDArray[Any] | tuple[str, ...] = tuple(
                cast(Sequence[str], self.values)
            )
            if not all(isinstance(value, str) for value in values):
                raise TypeError(f"{field} must be Python strings")
        else:
            values = _typed_array(self.values, _VECTOR_DTYPES[self.logical_type], field)
        valid = _typed_array(self.valid, np.bool_, "dense validity mask")
        if len(values) != self.rows * self.columns or len(valid) != len(values):
            raise ValueError("dense values, validity, and dimensions must agree")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "valid", valid)


LogicalValueComponent: TypeAlias = (
    LogicalComponent | LogicalDenseMatrix | LogicalSparseMatrix
)


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


@dataclass(frozen=True)
class DecodedSparseDatasetSplit:
    """A native sparse split and its four ordered logical components."""

    data: SparseDatasetSplit
    components: tuple[
        LogicalSparseMatrix,
        LogicalComponent,
        LogicalSparseMatrix,
        LogicalComponent,
    ]
