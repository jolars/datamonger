using Datamonger
using CodecBzip2
using CodecZlib
using DataFrames
using Dates
using HTTP
using JSON3
using SHA
using SparseArrays
using Test

include("test_canonical.jl")
include("test_decoders.jl")
include("test_registry.jl")
include("test_api.jl")
include("test_cache.jl")
