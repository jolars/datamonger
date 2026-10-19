module Datamonger

using CodecZlib
using DataFrames
using Dates
using FileWatching
using HTTP
using JSON3
using Libdl
using Pkg.Artifacts: artifact_exists, artifact_hash, artifact_path
using SHA
using SparseArrays
using TranscodingStreams

include("errors.jl")
include("models.jl")
include("native.jl")
include("canonical.jl")
include("decode.jl")
include("cache.jl")
include("registry.jl")
include("api.jl")
include("citations.jl")
include("preprocessing.jl")

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
    cite_data,
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
