"""Shared public and internal value objects."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
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
    """Immutable registry release identifier, such as ``"2026.09"``."""
    index_sha256: str
    """SHA-256 of the exact index bytes, as 64 lowercase hexadecimal digits."""
    index_url: str
    """Absolute HTTP or HTTPS URL used to retrieve an unbundled index."""
    schema_version: int = 1
    """Version of the registry selector schema; the client supports version 1."""


@dataclass(frozen=True)
class FetchInfo:
    """Reproducibility metadata for a completed fetch."""

    dataset_id: str
    """Resolved dataset identifier in ``source:name@version`` form."""
    registry_release: str
    """Immutable registry release used to resolve and verify this fetch."""
    registry_index_sha256: str
    """SHA-256 of the selected registry index's exact bytes."""
    artifact_digests: Mapping[str, str]
    """Artifact names mapped to the verified SHA-256 digests of their bytes."""
    verification: VerificationLevel
    """Completed verification level: ``"artifact"`` or ``"decoded"``."""
    canonical_form: int | None
    """Canonical-form version used for decoded verification, or ``None`` if skipped."""
    canonical_digest: str | None
    """Verified SHA-256 of the canonical decoded data, or ``None`` if skipped."""
    citations: tuple[Mapping[str, Any], ...] = ()
    """All curated references, including optional roles, notes, and recommendations."""
    citation_instructions: str | None = None
    """Recorded upstream citation instructions, or ``None`` when unavailable."""
    preprocessing: Mapping[str, Any] | None = None
    """Upstream and Datamonger processing history, or ``None`` when unrecorded."""


@dataclass(frozen=True)
class DataInfo:
    """Registry metadata for one resolved dataset version."""

    dataset_id: str
    """Resolved dataset identifier in ``source:name@version`` form."""
    source: str
    """Source namespace that identifies the dataset's provider or collection."""
    name: str
    """Dataset name within its source namespace, without a version suffix."""
    version: str
    """Exact dataset version selected explicitly or through the registry default."""
    registry_release: str
    """Immutable registry release containing this dataset record."""
    registry_index_sha256: str
    """SHA-256 of the selected registry index's exact bytes."""
    title: str
    """Human-readable dataset title supplied by the registry."""
    description: str
    """Registry prose describing the dataset's contents and purpose."""
    modality: str
    """Registry category for the data, such as ``"tabular"``."""
    provenance: Mapping[str, Any]
    """Registry record of the dataset's origin and upstream references."""
    license: Mapping[str, Any]
    """Registry record of the dataset's license and usage terms."""
    artifacts: tuple[Mapping[str, Any], ...]
    """Artifact records describing retrieval URLs, byte sizes, digests, and formats."""
    representation: Mapping[str, Any]
    """Decoder selection, options, artifact roles, and expected logical output."""
    expected_components: tuple[Mapping[str, Any], ...]
    """Declared component names, logical types, and shapes used in verification."""
    verification_records: tuple[Mapping[str, Any], ...]
    """Declared canonical-form versions and digests, without verifying decoded data."""
    related: tuple[Mapping[str, Any], ...]
    """Registry links to related datasets, or an empty tuple when none are declared."""
    tasks: tuple[Mapping[str, Any], ...]
    """Registry task descriptions, or an empty tuple when none are declared."""
    citations: tuple[Mapping[str, Any], ...] = ()
    """All curated references; an absent ``recommended`` flag means unknown."""
    citation_instructions: str | None = None
    """Recorded upstream citation instructions, or ``None`` when unavailable."""
    preprocessing: Mapping[str, Any] | None = None
    """Upstream and Datamonger processing history, or ``None`` when unrecorded."""


@dataclass(frozen=True)
class SparseDataset:
    """A named sparse feature matrix and its response vector."""

    features: sparse.csr_matrix
    """Float64 feature matrix in CSR format, with one row per observation."""
    response: ResponseArray
    """Int64 or float64 response vector aligned with the feature matrix's rows."""


@dataclass(frozen=True)
class SparseDatasetSplit:
    """Separate training and test sparse datasets from one representation."""

    train: SparseDataset
    """Training features and responses from the representation's training artifact."""
    test: SparseDataset
    """Test features and responses using the same feature dimension as training data."""


@dataclass(frozen=True)
class DatasetSplits(Mapping[str, pd.DataFrame | SparseDataset]):
    """Provider-named splits in recipe order, accessed as ``data["validation"]``.

    Each value is a table or sparse dataset. A table may contain only features
    when the provider does not supply labels for that split.
    """

    splits: Mapping[str, pd.DataFrame | SparseDataset]

    def __getitem__(self, name: str) -> pd.DataFrame | SparseDataset:
        return self.splits[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self.splits)

    def __len__(self) -> int:
        return len(self.splits)


DatasetData: TypeAlias = (
    pd.DataFrame | SparseDataset | SparseDatasetSplit | DatasetSplits
)


@dataclass(frozen=True)
class FetchResult:
    """Decoded data together with its reproducibility metadata."""

    data: DatasetData
    """Decoded table, sparse dataset, or collection of provider splits."""
    info: FetchInfo
    """Registry, artifact, and verification metadata for this completed fetch."""


@dataclass(frozen=True)
class CacheEntry:
    """One content-addressed object found in the Python client cache."""

    kind: CacheEntryKind
    """Object category: a dataset ``"artifact"`` or a ``"registry"`` index."""
    sha256: str
    """Expected SHA-256 digest encoded in the object's cache filename."""
    size: int
    """Size of the cached file in bytes at inspection time."""
    modified_at: datetime
    """File modification time as a timezone-aware UTC datetime."""
    path: Path
    """Local path to the content-addressed cached file."""
    valid: bool
    """Whether the inspected file's SHA-256 matches the digest in its filename."""
    datasets: tuple[str, ...]
    """Sorted dataset identifiers referencing this artifact in known registry indexes.

    Registry entries and artifacts with no known references have an empty tuple.
    References come from the bundled index and valid cached indexes.
    """
    registry_release: str | None
    """Release read from a valid cached registry index, or ``None`` if unavailable.

    Artifact entries always use ``None``.
    """


@dataclass(frozen=True)
class CacheInfo:
    """A point-in-time inventory of the Python client cache."""

    location: Path
    """Cache root inspected, whether or not the directory exists."""
    total_size: int
    """Sum of the inventoried files' sizes in bytes, including invalid entries."""
    entries: tuple[CacheEntry, ...]
    """Inspected registry and artifact entries, sorted by kind and expected digest."""


@dataclass(frozen=True)
class CacheCleanResult:
    """The entries removed or skipped by one manual cache eviction."""

    location: Path
    """Cache root from which matching objects were selected for eviction."""
    removed: tuple[CacheEntry, ...]
    """Entries actually deleted after acquiring their exclusive cache leases."""
    skipped: tuple[CacheEntry, ...]
    """Matching entries retained because another operation held an active lease."""

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


@dataclass(frozen=True)
class DecodedSplits:
    """Named native splits with their ordered, qualified logical components."""

    data: DatasetSplits
    components: tuple[LogicalValueComponent, ...]
