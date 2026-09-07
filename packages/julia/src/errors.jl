abstract type DatamongerError <: Exception end
abstract type RegistryError <: DatamongerError end
abstract type RetrievalError <: DatamongerError end

macro define_error(name, parent)
    quote
        struct $(esc(name)) <: $(esc(parent))
            message::String
        end
        Base.showerror(io::IO, error::$(esc(name))) = print(io, error.message)
    end
end

@define_error RegistryIntegrityError RegistryError
@define_error RegistryReleaseError RegistryError
@define_error UnsupportedRegistryError RegistryError
@define_error RegistryRetrievalError RegistryError
@define_error RegistryOfflineError RegistryError
@define_error UnknownDatasetError DatamongerError
@define_error ArtifactSelectionError RetrievalError
@define_error ArtifactUnavailableError RetrievalError
@define_error OfflineError RetrievalError
@define_error RetrievalLocationsError RetrievalError
@define_error ArtifactIntegrityError RetrievalError
@define_error CacheError DatamongerError
@define_error UnsupportedDecoderError DatamongerError
@define_error DecodeError DatamongerError
@define_error DecodedIntegrityError DatamongerError

const SEMANTIC_ERROR_CATEGORIES = Dict{String,DataType}(
    "unknown-dataset" => UnknownDatasetError,
    "unsupported-registry" => UnsupportedRegistryError,
    "unsupported-decoder" => UnsupportedDecoderError,
    "artifact-unavailable" => ArtifactUnavailableError,
    "artifact-offline" => OfflineError,
    "retrieval-exhausted" => RetrievalLocationsError,
    "artifact-integrity" => ArtifactIntegrityError,
    "decoded-integrity" => DecodedIntegrityError,
    "cache" => CacheError,
    "decode" => DecodeError,
)
