"""Datamonger Python reference client."""

from datamonger._api import fetch_data
from datamonger._models import (
    DatasetData,
    FetchInfo,
    FetchResult,
    Registry,
    SparseDataset,
)
from datamonger._registry import BUNDLED_REGISTRY, resolve_registry
from datamonger._selection import active_registry, set_registry

__all__ = [
    "BUNDLED_REGISTRY",
    "DatasetData",
    "FetchInfo",
    "FetchResult",
    "Registry",
    "SparseDataset",
    "active_registry",
    "fetch_data",
    "resolve_registry",
    "set_registry",
]
