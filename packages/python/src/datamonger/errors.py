"""Public semantic error taxonomy."""

from datamonger._errors import (
    ArtifactIntegrityError,
    CacheError,
    DatamongerError,
    DecodedIntegrityError,
    DecodeError,
    OfflineError,
    RegistryError,
    RegistryIntegrityError,
    RegistryOfflineError,
    RegistryReleaseError,
    RegistryRetrievalError,
    RetrievalError,
    UnknownDatasetError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
)

__all__ = [
    "ArtifactIntegrityError",
    "CacheError",
    "DatamongerError",
    "DecodeError",
    "DecodedIntegrityError",
    "OfflineError",
    "RegistryError",
    "RegistryIntegrityError",
    "RegistryOfflineError",
    "RegistryReleaseError",
    "RegistryRetrievalError",
    "RetrievalError",
    "UnknownDatasetError",
    "UnsupportedDecoderError",
    "UnsupportedRegistryError",
]
