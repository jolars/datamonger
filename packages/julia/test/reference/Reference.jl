"""Independent pre-migration Julia decoder and encoder; never loaded by the client."""
module Reference
using CodecBzip2, CodecZlib, DataFrames, SHA, SparseArrays, TranscodingStreams
using Datamonger: DatamongerError, DecodeError, UnsupportedDecoderError, DecodedIntegrityError,
    LogicalComponent, LogicalVector, LogicalDenseMatrix, LogicalSparseMatrix,
    Decoded, SparseDataset, SparseDatasetSplit, CSRMatrix
include("canonical.jl")
include("decode.jl")
end
