"""Semantic errors exposed by the Datamonger client."""


class DatamongerError(Exception):
    """Base class for expected Datamonger failures."""


class RegistryError(DatamongerError):
    """Base class for registry failures."""


class RegistryIntegrityError(RegistryError):
    """The registry bytes do not match the strong selector."""


class RegistryReleaseError(RegistryError):
    """The selected and embedded registry releases disagree."""


class UnsupportedRegistryError(RegistryError):
    """The registry uses an unsupported schema."""


class RegistryRetrievalError(RegistryError):
    """The registry index could not be retrieved."""


class RegistryOfflineError(RegistryRetrievalError):
    """A verified registry index is unavailable while offline."""


class UnknownDatasetError(DatamongerError):
    """The selected registry does not contain the requested dataset."""


class RetrievalError(DatamongerError):
    """Base class for artifact selection and retrieval failures."""


class ArtifactSelectionError(RetrievalError):
    """An artifact name is missing, ambiguous, or unknown."""


class ArtifactUnavailableError(RetrievalError):
    """Distribution policy prevents automatic artifact retrieval."""


class OfflineError(RetrievalError):
    """A verified artifact is unavailable while offline."""


class RetrievalLocationsError(RetrievalError):
    """Every artifact retrieval location failed without an integrity mismatch."""


class ArtifactIntegrityError(RetrievalError):
    """Retrieved artifact bytes fail size or digest verification."""


class CacheError(DatamongerError):
    """A cache object could not be read or published safely."""


class UnsupportedDecoderError(DatamongerError):
    """The representation requires unsupported decoder behavior."""


class DecodeError(DatamongerError):
    """Verified artifact bytes cannot be decoded by their recipe."""


class DecodedIntegrityError(DatamongerError):
    """Decoded logical values do not match the registry expectation."""
