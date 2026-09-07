module Datamonger

using CodecBzip2
using CodecZlib
using DataFrames
using Dates
using FileWatching
using HTTP
using JSON3
using SHA
using SparseArrays
using TranscodingStreams

include("errors.jl")
include("models.jl")
include("canonical.jl")
include("decode.jl")
include("cache.jl")
include("registry.jl")
include("api.jl")

export ArtifactIntegrityError,
    ArtifactSelectionError,
    ArtifactUnavailableError,
    BUNDLED_REGISTRY,
    CacheCleanResult,
    CacheEntry,
    CacheError,
    CacheInfo,
    CSRMatrix,
    DataInfo,
    DatamongerError,
    DecodeError,
    DecodedIntegrityError,
    FetchInfo,
    FetchResult,
    OfflineError,
    Registry,
    RegistryError,
    RegistryIntegrityError,
    RegistryOfflineError,
    RegistryReleaseError,
    RegistryRetrievalError,
    RetrievalError,
    RetrievalLocationsError,
    SparseDataset,
    SparseDatasetSplit,
    UnknownDatasetError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
    active_registry,
    cache_clean,
    cache_info,
    data_info,
    datamonger_cache_dir,
    default_cache_dir,
    fetch_artifact,
    fetch_data,
    list_data,
    registry_selector,
    resolve_registry,
    set_registry,
    set_registry!

end
