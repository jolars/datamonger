const _KIND_TAGS = Dict("vector" => 0x01, "sparse_matrix" => 0x02, "dense_matrix" => 0x03)
const _TYPE_TAGS = Dict("float64" => 0x01, "int64" => 0x02, "string" => 0x03, "bool" => 0x04)

_kind(::LogicalVector) = "vector"
_kind(::LogicalDenseMatrix) = "dense_matrix"
_kind(::LogicalSparseMatrix) = "sparse_matrix"
_logical_type(component::Union{LogicalVector,LogicalDenseMatrix}) = component.logical_type
_logical_type(::LogicalSparseMatrix) = "float64"

function _write_uint(io, ::Type{T}, value::Integer) where {T<:Unsigned}
    0 <= value <= typemax(T) || throw(DecodedIntegrityError("canonical integer is out of range"))
    write(io, htol(T(value)))
end

function _write_header(io, component::LogicalComponent)
    isvalid(component.name) ||
        throw(DecodedIntegrityError("component names must be valid UTF-8"))
    name = Vector{UInt8}(codeunits(component.name))
    isempty(name) && throw(DecodedIntegrityError("component names must be nonempty"))
    _write_uint(io, UInt32, length(name))
    write(io, name)
    write(io, UInt8(_KIND_TAGS[_kind(component)]))
    write(io, UInt8(_TYPE_TAGS[_logical_type(component)]))
end

function _bitmap(values)
    bytes = zeros(UInt8, cld(length(values), 8))
    for (index, value) in enumerate(values)
        value && (bytes[(index - 1) ÷ 8 + 1] |= UInt8(1) << ((index - 1) % 8))
    end
    return bytes
end

function _write_float(io, value::Float64)
    word = if isnan(value)
        UInt64(0x7ff8000000000000)
    elseif value == 0.0
        UInt64(0)
    else
        reinterpret(UInt64, value)
    end
    write(io, htol(word))
end

function _write_values(io, component::Union{LogicalVector,LogicalDenseMatrix})
    write(io, _bitmap(component.valid))
    if component.logical_type == "float64"
        for (value, valid) in zip(component.values, component.valid)
            _write_float(io, valid ? Float64(value) : 0.0)
        end
    elseif component.logical_type == "int64"
        for (value, valid) in zip(component.values, component.valid)
            write(io, htol(valid ? Int64(value) : Int64(0)))
        end
    elseif component.logical_type == "string"
        for (value, valid) in zip(component.values, component.valid)
            string_value = valid ? String(value) : ""
            isvalid(string_value) ||
                throw(DecodedIntegrityError("logical strings must be valid UTF-8"))
            bytes = Vector{UInt8}(codeunits(string_value))
            _write_uint(io, UInt64, length(bytes))
            write(io, bytes)
        end
    elseif component.logical_type == "bool"
        values = [valid && Bool(value) for (value, valid) in zip(component.values, component.valid)]
        write(io, _bitmap(values))
    else
        throw(DecodedIntegrityError("unsupported canonical element type"))
    end
end

function _write_component(io, component::LogicalVector)
    _write_header(io, component)
    write(io, UInt8(1))
    _write_uint(io, UInt64, length(component.values))
    _write_values(io, component)
end

function _write_component(io, component::LogicalDenseMatrix)
    _write_header(io, component)
    write(io, UInt8(2))
    _write_uint(io, UInt64, component.rows)
    _write_uint(io, UInt64, component.columns)
    _write_values(io, component)
end

function _write_component(io, component::LogicalSparseMatrix)
    _write_header(io, component)
    write(io, UInt8(2))
    nonzeros = length(component.values)
    component.rows >= 0 && component.columns >= 0 ||
        throw(DecodedIntegrityError("sparse dimensions must be nonnegative"))
    length(component.row_offsets) == component.rows + 1 ||
        throw(DecodedIntegrityError("sparse row offsets have the wrong length"))
    length(component.column_indices) == nonzeros ||
        throw(DecodedIntegrityError("sparse indices and values must have equal lengths"))
    first(component.row_offsets) == 0 && last(component.row_offsets) == nonzeros ||
        throw(DecodedIntegrityError("sparse row offsets have invalid bounds"))
    all(offset -> 0 <= offset <= nonzeros, component.row_offsets) &&
        issorted(component.row_offsets) ||
        throw(DecodedIntegrityError("sparse row offsets are not canonical"))
    _write_uint(io, UInt64, component.rows)
    _write_uint(io, UInt64, component.columns)
    _write_uint(io, UInt64, nonzeros)
    for offset in component.row_offsets
        _write_uint(io, UInt64, offset)
    end
    for row in 1:component.rows
        lower = component.row_offsets[row] + 1
        upper = component.row_offsets[row + 1]
        previous = -1
        for position in lower:upper
            column = component.column_indices[position]
            0 <= column < component.columns && column > previous ||
                throw(DecodedIntegrityError("sparse column indices are not canonical"))
            previous = column
        end
    end
    for column in component.column_indices
        _write_uint(io, UInt64, column)
    end
    for value in component.values
        !isinf(value) && value != 0.0 ||
            throw(DecodedIntegrityError("sparse values must be nonzero and not infinite"))
        _write_float(io, value)
    end
end

function canonical_bytes(components)
    length(components) <= typemax(UInt32) ||
        throw(DecodedIntegrityError("too many canonical components"))
    names = [component.name for component in components]
    length(unique(names)) == length(names) ||
        throw(DecodedIntegrityError("canonical component names must be unique"))
    io = IOBuffer()
    write(io, codeunits("DMCF"))
    _write_uint(io, UInt16, 1)
    _write_uint(io, UInt32, length(components))
    for component in components
        _write_component(io, component)
    end
    return take!(io)
end

canonical_sha256(components) = bytes2hex(sha256(canonical_bytes(components)))

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
