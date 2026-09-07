"""A release location and strong selector for one immutable registry index."""
struct Registry
    release::String
    index_sha256::String
    index_url::String
    schema_version::Int

    function Registry(release, index_sha256, index_url, schema_version=1)
        release isa AbstractString && index_sha256 isa AbstractString &&
            index_url isa AbstractString ||
            throw(RegistryRetrievalError("registry selector fields must be strings"))
        schema_version isa Integer && !(schema_version isa Bool) ||
            throw(UnsupportedRegistryError("selector schema version must be an integer"))
        registry = new(
            String(release),
            String(index_sha256),
            String(index_url),
            Int(schema_version),
        )
        validate_registry_selector(registry)
        return registry
    end
end

"""Reproducibility metadata for a completed fetch."""
struct FetchInfo
    dataset_id::String
    registry_release::String
    registry_index_sha256::String
    artifact_digests::Dict{String,String}
    verification::Symbol
    canonical_form::Union{Nothing,Int}
    canonical_digest::Union{Nothing,String}
end

"""Registry metadata for one resolved dataset version."""
struct DataInfo
    dataset_id::String
    source::String
    name::String
    version::String
    registry_release::String
    registry_index_sha256::String
    title::String
    description::String
    modality::String
    provenance::Dict{String,Any}
    license::Dict{String,Any}
    artifacts::Vector{Dict{String,Any}}
    representation::Dict{String,Any}
    expected_components::Vector{Dict{String,Any}}
    verification_records::Vector{Dict{String,Any}}
    related::Vector{Dict{String,Any}}
    tasks::Vector{Dict{String,Any}}
end

"""A read-only row-compressed sparse matrix for exceptionally wide data."""
struct CSRMatrix <: AbstractMatrix{Float64}
    rows::Int
    columns::Int
    row_offsets::Vector{Int}
    column_indices::Vector{Int}
    values::Vector{Float64}
end

Base.size(matrix::CSRMatrix) = (matrix.rows, matrix.columns)
SparseArrays.nnz(matrix::CSRMatrix) = length(matrix.values)

function Base.getindex(matrix::CSRMatrix, row::Int, column::Int)
    checkbounds(matrix, row, column)
    lower = matrix.row_offsets[row] + 1
    upper = matrix.row_offsets[row + 1]
    target = column - 1
    position = lower + searchsortedfirst(@view(matrix.column_indices[lower:upper]), target) - 1
    return position <= upper && matrix.column_indices[position] == target ?
           matrix.values[position] : 0.0
end

"""A sparse feature matrix and its exact response vector."""
struct SparseDataset{T<:Union{Int64,Float64},M<:AbstractMatrix{Float64}}
    features::M
    response::Vector{T}
end

"""Separate training and test sparse datasets."""
struct SparseDatasetSplit{T<:Union{Int64,Float64},M1<:AbstractMatrix{Float64},M2<:AbstractMatrix{Float64}}
    train::SparseDataset{T,M1}
    test::SparseDataset{T,M2}
end

"""Decoded data together with its reproducibility metadata."""
struct FetchResult{T}
    data::T
    info::FetchInfo
end

"""One inspected registry or artifact cache entry."""
struct CacheEntry
    kind::Symbol
    sha256::String
    size::Int64
    modified_at::DateTime
    path::String
    valid::Bool
    datasets::Vector{String}
    registry_release::Union{Nothing,String}
end

"""A point-in-time inventory of the Julia client's cache."""
struct CacheInfo
    location::String
    total_size::Int64
    entries::Vector{CacheEntry}
end

"""The entries removed or skipped by manual cache eviction."""
struct CacheCleanResult
    location::String
    removed::Vector{CacheEntry}
    skipped::Vector{CacheEntry}
    bytes_removed::Int64
end

abstract type LogicalComponent end

struct LogicalVector <: LogicalComponent
    name::String
    logical_type::String
    values::AbstractVector
    valid::BitVector

    function LogicalVector(name, logical_type, values, valid)
        length(values) == length(valid) ||
            throw(ArgumentError("logical values and validity must have equal lengths"))
        return new(String(name), String(logical_type), values, BitVector(valid))
    end
end

struct LogicalDenseMatrix <: LogicalComponent
    name::String
    logical_type::String
    rows::Int
    columns::Int
    values::AbstractVector
    valid::BitVector

    function LogicalDenseMatrix(name, logical_type, rows, columns, values, valid)
        rows >= 0 && columns >= 0 ||
            throw(ArgumentError("dense dimensions must be nonnegative"))
        length(values) == rows * columns == length(valid) ||
            throw(ArgumentError("dense values, validity, and dimensions must agree"))
        return new(
            String(name),
            String(logical_type),
            Int(rows),
            Int(columns),
            values,
            BitVector(valid),
        )
    end
end

struct LogicalSparseMatrix <: LogicalComponent
    name::String
    rows::Int
    columns::Int
    row_offsets::Vector{Int}
    column_indices::Vector{Int}
    values::Vector{Float64}
end

struct Decoded{T,C<:Tuple}
    data::T
    components::C
end
