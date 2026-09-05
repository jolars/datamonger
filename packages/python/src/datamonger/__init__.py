"""Datamonger Python reference client."""

from datamonger._api import data_info, fetch_artifact, fetch_data, list_data
from datamonger._cache_management import cache_clean, cache_info
from datamonger._models import (
    CacheCleanResult,
    CacheEntry,
    CacheInfo,
    DataInfo,
    DatasetData,
    FetchInfo,
    FetchResult,
    Registry,
    SparseDataset,
    SparseDatasetSplit,
)
from datamonger._registry import BUNDLED_REGISTRY, resolve_registry
from datamonger._selection import active_registry, set_registry

__all__ = [
    "BUNDLED_REGISTRY",
    "CacheCleanResult",
    "CacheEntry",
    "CacheInfo",
    "DataInfo",
    "DatasetData",
    "FetchInfo",
    "FetchResult",
    "Registry",
    "SparseDataset",
    "SparseDatasetSplit",
    "active_registry",
    "cache_clean",
    "cache_info",
    "data_info",
    "fetch_artifact",
    "fetch_data",
    "list_data",
    "resolve_registry",
    "set_registry",
]
