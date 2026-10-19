# These isbits layouts mirror C ABI 1 in datamonger.h. All input buffers are
# rooted through each call, and every result is copied before its Rust owner dies.
struct _NativeBytes
    data::Ptr{UInt8}
    len::Csize_t
end
_NativeBytes(value::Union{String,Vector{UInt8}}) = _NativeBytes(pointer(value), sizeof(value))
const _EMPTY_BYTES = _NativeBytes(C_NULL, 0)

struct _NativeU64s
    data::Ptr{UInt64}
    len::Csize_t
end
_NativeU64s(values::Vector{UInt64}) = _NativeU64s(pointer(values), length(values))
const _EMPTY_U64S = _NativeU64s(C_NULL, 0)

struct _NativeColumn
    name::_NativeBytes
    data_type::UInt32
end
struct _NativeDelimitedOptions
    delimiter::UInt32
    columns::Ptr{_NativeColumn}
    column_count::Csize_t
    missing_values::Ptr{_NativeBytes}
    missing_count::Csize_t
end
struct _NativeLibsvmOptions
    feature_count::UInt64
    label_type::UInt32
    target_name::_NativeBytes
end
struct _NativeArtifact
    path::_NativeBytes
    compression::UInt32
end
struct _NativeComponent
    name::_NativeBytes
    kind::UInt32
    data_type::UInt32
    rows::UInt64
    columns::UInt64
    values::Ptr{Cvoid}
    len::Csize_t
    valid::_NativeBytes
    row_offsets::_NativeU64s
    column_indices::_NativeU64s
end

const _NATIVE_TYPES = Dict("float64" => UInt32(1), "int64" => UInt32(2),
                           "string" => UInt32(3), "bool" => UInt32(4))
const _NATIVE_LIBRARY = Ref{Ptr{Cvoid}}(C_NULL)
const _NATIVE_LOCK = ReentrantLock()

function _native_library_path(artifact_toml)
    hash = artifact_hash("datamonger_core", artifact_toml)
    hash === nothing && error(
        "No Datamonger native artifact for this platform. " *
        "For a source checkout, run tools/dm_julia_core.jl with Julia.",
    )
    # Package installation owns executable downloads, including when the first
    # decode is offline. Runtime calls must never initiate that installation.
    artifact_exists(hash) || error(
        "Datamonger native artifact is not installed. Run Pkg.instantiate() " *
        "before fetching data, or rebuild the local artifact in a source checkout.",
    )
    return joinpath(artifact_path(hash), "lib", "datamonger_ffi.$(Libdl.dlext)")
end

function _native_symbol(name)
    lock(_NATIVE_LOCK) do
        if _NATIVE_LIBRARY[] == C_NULL
            path = get(ENV, "DM_JULIA_CORE_LIBRARY", "")
            if isempty(path)
                local_toml = joinpath(@__DIR__, "..", "deps", "Artifacts.toml")
                artifact_toml = isfile(local_toml) ? local_toml : joinpath(@__DIR__, "..", "Artifacts.toml")
                path = _native_library_path(artifact_toml)
            end
            handle = Libdl.dlopen(path)
            version = try
                ccall(Libdl.dlsym(handle, :dm_abi_version), UInt32, ())
            catch
                Libdl.dlclose(handle)
                rethrow()
            end
            if version != 1
                Libdl.dlclose(handle)
                error("Unsupported Datamonger C ABI $version; expected 1")
            end
            _NATIVE_LIBRARY[] = handle
        end
        return Libdl.dlsym(_NATIVE_LIBRARY[], name)
    end
end

function _copy_native(::Type{T}, data::Ptr, len::Integer) where {T}
    len == 0 && return T[]
    return copy(unsafe_wrap(Vector{T}, Ptr{T}(data), Int(len); own=false))
end
_copy_native(bytes::_NativeBytes) = _copy_native(UInt8, bytes.data, bytes.len)
_native_string(bytes::_NativeBytes) = String(_copy_native(bytes))

function _with_native_result(f, result; canonical=false)
    result == C_NULL && error("Datamonger native library returned a null result")
    try
        status = ccall(_native_symbol(:dm_result_status), UInt32, (Ptr{Cvoid},), result)
        if status != 0
            message = _native_string(ccall(
                _native_symbol(:dm_result_error), _NativeBytes, (Ptr{Cvoid},), result,
            ))
            status == 1 && throw(UnsupportedDecoderError(message))
            status == 3 && throw(DecodedIntegrityError(message))
            status == 2 && throw(canonical ? DecodedIntegrityError(message) : DecodeError(message))
            error("Datamonger native library failed: $message")
        end
        return f(result)
    finally
        ccall(_native_symbol(:dm_result_free), Cvoid, (Ptr{Cvoid},), result)
    end
end

function _native_components(result)
    count = ccall(_native_symbol(:dm_result_count), Csize_t, (Ptr{Cvoid},), result)
    return Tuple(map(0:(Int(count) - 1)) do index
        view = unsafe_load(ccall(
            _native_symbol(:dm_result_component), Ptr{_NativeComponent},
            (Ptr{Cvoid}, Csize_t), result, index,
        ))
        name = _native_string(view.name)
        values = if view.data_type == 1
            _copy_native(Float64, view.values, view.len)
        elseif view.data_type == 2
            _copy_native(Int64, view.values, view.len)
        elseif view.data_type == 3
            _native_string.(_copy_native(_NativeBytes, view.values, view.len))
        else
            Bool.(_copy_native(UInt8, view.values, view.len))
        end
        if view.kind == 2
            return LogicalSparseMatrix(
                name, Int(view.rows), Int(view.columns),
                Int.(_copy_native(UInt64, view.row_offsets.data, view.row_offsets.len)),
                Int.(_copy_native(UInt64, view.column_indices.data, view.column_indices.len)),
                values,
            )
        end
        logical_type = ("float64", "int64", "string", "bool")[view.data_type]
        valid = Bool.(_copy_native(view.valid))
        if view.kind == 1
            return LogicalVector(name, logical_type, values, valid)
        end
        return LogicalDenseMatrix(name, logical_type, Int(view.rows), Int(view.columns), values, valid)
    end)
end

function _native_artifact(path::String, compression)
    tag = compression == "none" ? 0 : compression == "gzip" ? 1 :
          compression == "bzip2" ? 2 :
          throw(UnsupportedDecoderError("unsupported artifact compression '$compression'"))
    return _NativeArtifact(_NativeBytes(path), tag)
end

function _native_canonical(components, emit_bytes)
    roots = Any[]
    views = _NativeComponent[]
    for component in components
        name = component.name
        isvalid(name) || throw(DecodedIntegrityError("component names must be valid UTF-8"))
        tag = get(_NATIVE_TYPES, _logical_type(component), nothing)
        tag === nothing && throw(DecodedIntegrityError("unsupported canonical element type"))
        if component isa LogicalSparseMatrix
            component.rows >= 0 && component.columns >= 0 &&
                all(>=(0), component.row_offsets) && all(>=(0), component.column_indices) ||
                throw(DecodedIntegrityError("negative sparse dimensions or indices"))
            kind = 2
            rows, columns = component.rows, component.columns
            offsets = UInt64.(component.row_offsets)
            indices = UInt64.(component.column_indices)
            valid = UInt8[]
        else
            kind = component isa LogicalVector ? 1 : 3
            rows = kind == 1 ? length(component.values) : component.rows
            columns = kind == 1 ? 1 : component.columns
            offsets, indices = UInt64[], UInt64[]
            valid = UInt8.(component.valid)
        end
        string_values = String[]
        values = if component isa LogicalSparseMatrix
            Float64.(component.values)
        elseif tag == 1
            Float64[present ? Float64(value) : 0.0
                    for (value, present) in zip(component.values, component.valid)]
        elseif tag == 2
            Int64[present ? Int64(value) : Int64(0)
                  for (value, present) in zip(component.values, component.valid)]
        elseif tag == 3
            for (value, present) in zip(component.values, component.valid)
                text = present ? String(value) : ""
                isvalid(text) || throw(DecodedIntegrityError("logical strings must be valid UTF-8"))
                push!(string_values, text)
            end
            _NativeBytes.(string_values)
        else
            UInt8[present ? UInt8(value) : 0x00
                  for (value, present) in zip(component.values, component.valid)]
        end
        append!(roots, (name, values, string_values, valid, offsets, indices))
        push!(views, _NativeComponent(
            _NativeBytes(name), kind, tag, rows, columns, pointer(values), length(values),
            _NativeBytes(valid), _NativeU64s(offsets), _NativeU64s(indices),
        ))
    end
    GC.@preserve roots views begin
        result = ccall(_native_symbol(:dm_canonical), Ptr{Cvoid},
            (Ptr{_NativeComponent}, Csize_t, UInt32), views, length(views), emit_bytes)
        return _with_native_result(result; canonical=true) do result
            symbol = emit_bytes ? :dm_result_bytes : :dm_result_digest
            return _copy_native(ccall(_native_symbol(symbol), _NativeBytes, (Ptr{Cvoid},), result))
        end
    end
end
