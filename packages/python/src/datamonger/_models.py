"""Shared public and internal value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from typing import Literal, TypeAlias, TypeVar, cast

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


_Scalar = TypeVar("_Scalar", np.int64, np.float64)


def _typed_array(
    value: object, dtype: type[_Scalar], field: str
) -> npt.NDArray[_Scalar]:
    array = np.asarray(value)
    if array.ndim != 1:
        raise ValueError(f"sparse {field} must be one-dimensional")
    if array.dtype == dtype:
        return cast(npt.NDArray[_Scalar], array)
    if array.size == 0:
        return np.zeros(0, dtype=dtype)
    try:
        return array.astype(dtype, casting="safe")
    except TypeError as error:
        raise TypeError(f"sparse {field} must have {dtype.__name__} values") from error


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
