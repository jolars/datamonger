function _validate_delimited_options(options::AbstractDict)
    required = Set(["encoding", "delimiter", "header", "quote", "escape", "row_order", "columns"])
    allowed = union(required, Set(["missing_values"]))
    keys_set = Set(String.(keys(options)))
    issubset(required, keys_set) && issubset(keys_set, allowed) ||
        throw(UnsupportedDecoderError("invalid delimited-text option fields"))
    options["encoding"] == "utf-8" && options["header"] === true &&
        options["quote"] == "\"" && options["escape"] == "double" &&
        options["row_order"] == "source" ||
        throw(UnsupportedDecoderError("unsupported delimited-text options"))
    delimiter_string = options["delimiter"]
    delimiter_string in (",", "\t") ||
        throw(UnsupportedDecoderError("unsupported delimiter"))
    columns = options["columns"]
    columns isa AbstractVector && !isempty(columns) ||
        throw(UnsupportedDecoderError("columns must be a nonempty array"))
    names = String[]
    types = String[]
    for column in columns
        column isa AbstractDict && Set(String.(keys(column))) == Set(["name", "type"]) ||
            throw(UnsupportedDecoderError("invalid column recipe"))
        name = get(column, "name", nothing)
        logical_type = get(column, "type", nothing)
        name isa String && !isempty(name) ||
            throw(UnsupportedDecoderError("column names must be nonempty strings"))
        logical_type in ("float64", "int64", "string", "bool") ||
            throw(UnsupportedDecoderError("unsupported logical column type"))
        push!(names, name)
        push!(types, logical_type)
    end
    length(unique(names)) == length(names) ||
        throw(UnsupportedDecoderError("column names must be unique"))
    missing_values = get(options, "missing_values", Any[])
    missing_values isa AbstractVector && all(value -> value isa String, missing_values) ||
        throw(UnsupportedDecoderError("missing_values must be an array of strings"))
    length(unique(missing_values)) == length(missing_values) ||
        throw(UnsupportedDecoderError("missing values must be unique"))
    return (UInt8(delimiter_string == "," ? ',' : '\t'), names, types, Set(String.(missing_values)))
end

function _validate_libsvm_options(options::AbstractDict)
    expected = Set([
        "index_base",
        "feature_count",
        "duplicate_features",
        "label_type",
        "row_order",
        "target_name",
    ])
    Set(String.(keys(options))) == expected ||
        throw(UnsupportedDecoderError("invalid LIBSVM option fields"))
    options["index_base"] === 1 && options["duplicate_features"] == "error" &&
        options["row_order"] == "source" ||
        throw(UnsupportedDecoderError("unsupported LIBSVM options"))
    feature_count = options["feature_count"]
    feature_count isa Integer && !(feature_count isa Bool) &&
        1 <= feature_count <= 9007199254740991 ||
        throw(UnsupportedDecoderError("feature_count is invalid"))
    label_type = options["label_type"]
    label_type in ("int64", "float64") ||
        throw(UnsupportedDecoderError("label_type is invalid"))
    target_name = options["target_name"]
    target_name isa String && !isempty(target_name) && target_name != "features" ||
        throw(UnsupportedDecoderError("target_name is invalid"))
    return (Int(feature_count), String(label_type), target_name)
end

function decode_delimited(path, options::AbstractDict; compression="none")
    delimiter, names, types, missing_values = _validate_delimited_options(options)
    path = String(path)
    missing_strings = collect(missing_values)
    missing_views = _NativeBytes.(missing_strings)
    columns = [_NativeColumn(_NativeBytes(name), _NATIVE_TYPES[type]) for (name, type) in zip(names, types)]
    artifact = _native_artifact(path, compression)
    GC.@preserve path names missing_strings missing_views columns begin
        recipe = _NativeDelimitedOptions(delimiter, pointer(columns), length(columns),
                                         pointer(missing_views), length(missing_views))
        result = ccall(_native_symbol(:dm_decode_delimited), Ptr{Cvoid},
                       (_NativeArtifact, _NativeDelimitedOptions), artifact, recipe)
        components = _with_native_result(_native_components, result)
        native = map(components) do component
            T = eltype(component.values)
            values = Vector{Union{Missing,T}}(undef, length(component.values))
            for index in eachindex(values)
                values[index] = component.valid[index] ? component.values[index] : missing
            end
            Symbol(component.name) => values
        end
        return Decoded(DataFrame(collect(native)), components)
    end
end

function _sparse_dataset(features, response)
    matrix = if features.columns <= 10_000_000
        rows = Int[]
        for row in 1:features.rows
            append!(rows, fill(row, features.row_offsets[row + 1] - features.row_offsets[row]))
        end
        sparse(rows, features.column_indices .+ 1, features.values, features.rows, features.columns)
    else
        CSRMatrix(features.rows, features.columns, features.row_offsets,
                  features.column_indices, features.values)
    end
    return SparseDataset(matrix, response.values)
end

function decode_libsvm(path, options::AbstractDict;
                       compression="none", prefix="", decoder_version=1)
    typeof(decoder_version) === Int && decoder_version in (1, 2) ||
        throw(UnsupportedDecoderError("unsupported LIBSVM version"))
    feature_count, label_type, target_name = _validate_libsvm_options(options)
    path, prefix = String(path), String(prefix)
    artifact = _native_artifact(path, compression)
    GC.@preserve path prefix target_name begin
        recipe = _NativeLibsvmOptions(feature_count, _NATIVE_TYPES[label_type], _NativeBytes(target_name))
        symbol = decoder_version == 2 ? :dm_decode_libsvm_v2 : :dm_decode_libsvm
        result = ccall(_native_symbol(symbol), Ptr{Cvoid},
            (_NativeArtifact, _NativeLibsvmOptions, _NativeBytes), artifact, recipe, _NativeBytes(prefix))
        components = _with_native_result(_native_components, result)
        return Decoded(_sparse_dataset(components...), components)
    end
end

function decode_libsvm_split(train_path, test_path, options::AbstractDict;
                             train_compression="none", test_compression="none", decoder_version=1)
    typeof(decoder_version) === Int && decoder_version in (1, 2) ||
        throw(UnsupportedDecoderError("unsupported LIBSVM version"))
    feature_count, label_type, target_name = _validate_libsvm_options(options)
    train_path, test_path = String(train_path), String(test_path)
    train = _native_artifact(train_path, train_compression)
    test = _native_artifact(test_path, test_compression)
    GC.@preserve train_path test_path target_name begin
        recipe = _NativeLibsvmOptions(feature_count, _NATIVE_TYPES[label_type], _NativeBytes(target_name))
        symbol = decoder_version == 2 ? :dm_decode_libsvm_split_v2 : :dm_decode_libsvm_split
        result = ccall(_native_symbol(symbol), Ptr{Cvoid},
            (_NativeArtifact, _NativeArtifact, _NativeLibsvmOptions), train, test, recipe)
        components = _with_native_result(_native_components, result)
        data = SparseDatasetSplit(_sparse_dataset(components[1:2]...), _sparse_dataset(components[3:4]...))
        return Decoded(data, components)
    end
end
