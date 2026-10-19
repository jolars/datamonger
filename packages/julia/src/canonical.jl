_kind(::LogicalVector) = "vector"
_kind(::LogicalDenseMatrix) = "dense_matrix"
_kind(::LogicalSparseMatrix) = "sparse_matrix"
_logical_type(component::Union{LogicalVector,LogicalDenseMatrix}) = component.logical_type
_logical_type(::LogicalSparseMatrix) = "float64"

function component_from_descriptor(descriptor::AbstractDict)
    kind = descriptor["kind"]
    logical_type = descriptor["type"]
    values = descriptor["values"]
    if kind == "sparse_matrix"
        return LogicalSparseMatrix(
            descriptor["name"],
            Int(descriptor["rows"]),
            Int(descriptor["columns"]),
            Int.(descriptor["row_offsets"]),
            Int.(descriptor["column_indices"]),
            Float64.(descriptor["values"]),
        )
    end
    valid = Bool.(descriptor["valid"])
    converted = if logical_type == "float64"
        [
            value == "-zero" ? -0.0 :
            value == "nan" ? NaN :
            value == "invalid" ? 0.0 : Float64(value) for value in values
        ]
    elseif logical_type == "int64"
        Int64.(values)
    elseif logical_type == "string"
        String.(values)
    elseif logical_type == "bool"
        Bool.(values)
    else
        throw(ArgumentError("unsupported descriptor type"))
    end
    if kind == "vector"
        return LogicalVector(descriptor["name"], logical_type, converted, valid)
    elseif kind == "dense_matrix"
        return LogicalDenseMatrix(
            descriptor["name"],
            logical_type,
            Int(descriptor["rows"]),
            Int(descriptor["columns"]),
            converted,
            valid,
        )
    end
    throw(ArgumentError("unsupported descriptor kind"))
end

canonical_bytes(components) = _native_canonical(components, true)
canonical_sha256(components) = bytes2hex(_native_canonical(components, false))
