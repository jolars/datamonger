"""Public semantic error taxonomy."""

from datamonger._errors import (
    ArtifactIntegrityError,
    CacheError,
    DatamongerError,
    DecodedIntegrityError,
    DecodeError,
    RegistryError,
    RegistryIntegrityError,
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
    "RegistryError",
    "RegistryIntegrityError",
    "RegistryReleaseError",
    "RegistryRetrievalError",
    "RetrievalError",
    "UnknownDatasetError",
    "UnsupportedDecoderError",
    "UnsupportedRegistryError",
]
