const _FLOAT_PATTERN = r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$"
const _SVM_FLOAT_PATTERN = r"^[+-]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$"
const _INT_PATTERN = r"^-?(0|[1-9][0-9]*)$"
const _SVM_INT_PATTERN = r"^[+-]?(0|[1-9][0-9]*)$"
const _INDEX_PATTERN = r"^(0|[1-9][0-9]*)$"

function _decompressed_bytes(path, compression)
    compression in ("none", "gzip", "bzip2") ||
        throw(UnsupportedDecoderError("unsupported artifact compression '$compression'"))
    bytes = try
        read(path)
    catch error
        throw(DecodeError("cannot read artifact: $(sprint(showerror, error))"))
    end
    compression == "none" && return bytes
    stream = try
        if compression == "gzip"
            GzipDecompressorStream(IOBuffer(bytes); gziponly=true)
        elseif compression == "bzip2"
            Bzip2DecompressorStream(IOBuffer(bytes))
        end
    catch error
        error isa DatamongerError && rethrow()
        throw(DecodeError("cannot initialize artifact decompression: $(sprint(showerror, error))"))
    end
    try
        return read(stream)
    catch error
        throw(DecodeError("malformed compressed artifact: $(sprint(showerror, error))"))
    finally
        try
            close(stream)
        catch
        end
    end
end

function _validated_text(bytes)
    length(bytes) >= 3 && bytes[1:3] == UInt8[0xef, 0xbb, 0xbf] &&
        throw(DecodeError("UTF-8 byte-order marks are invalid"))
    isvalid(String, bytes) || throw(DecodeError("artifact is not valid UTF-8"))
    return nothing
end

function _physical_records(bytes; empty_allowed)
    isempty(bytes) && return empty_allowed ? Vector{Vector{UInt8}}() :
                             throw(DecodeError("empty delimited artifact"))
    records = Vector{Vector{UInt8}}()
    start = 1
    for index in eachindex(bytes)
        byte = bytes[index]
        if byte == 0x0d
            index < length(bytes) && bytes[index + 1] == 0x0a ||
                throw(DecodeError("bare carriage return is invalid"))
        elseif byte == 0x0a
            stop = index > start && bytes[index - 1] == 0x0d ? index - 2 : index - 1
            push!(records, stop >= start ? bytes[start:stop] : UInt8[])
            start = index + 1
        end
    end
    start <= length(bytes) && push!(records, bytes[start:end])
    return records
end

function _parse_fields(record::Vector{UInt8}, delimiter::UInt8)
    fields = Vector{Vector{UInt8}}()
    position = 1
    while true
        if position > length(record)
            push!(fields, UInt8[])
            break
        elseif record[position] == 0x22
            position += 1
            field = UInt8[]
            closed = false
            while position <= length(record)
                if record[position] == 0x22
                    if position < length(record) && record[position + 1] == 0x22
                        push!(field, 0x22)
                        position += 2
                    else
                        closed = true
                        position += 1
                        break
                    end
                else
                    push!(field, record[position])
                    position += 1
                end
            end
            closed || throw(DecodeError("unterminated quoted field"))
            if position <= length(record) && record[position] != delimiter
                throw(DecodeError("closing quote must precede a delimiter or record end"))
            end
            push!(fields, field)
        else
            start = position
            while position <= length(record) && record[position] != delimiter
                record[position] == 0x22 &&
                    throw(DecodeError("quote in an unquoted field"))
                position += 1
            end
            push!(fields, record[start:(position - 1)])
        end
        position > length(record) && break
        position += 1
        if position > length(record)
            push!(fields, UInt8[])
            break
        end
    end
    return fields
end

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

function _parse_delimited_value(value::String, logical_type::String)
    if logical_type == "float64"
        occursin(_FLOAT_PATTERN, value) || throw(DecodeError("invalid float64 value '$value'"))
        parsed = tryparse(Float64, value)
        parsed !== nothing && isfinite(parsed) || throw(DecodeError("invalid float64 value '$value'"))
        return parsed
    elseif logical_type == "int64"
        occursin(_INT_PATTERN, value) || throw(DecodeError("invalid int64 value '$value'"))
        parsed = tryparse(Int64, value)
        parsed !== nothing || throw(DecodeError("int64 value is out of range"))
        return parsed
    elseif logical_type == "bool"
        value == "true" && return true
        value == "false" && return false
        throw(DecodeError("invalid bool value '$value'"))
    end
    return value
end

function decode_delimited(path, options::AbstractDict; compression="none")
    delimiter, names, types, missing_values = _validate_delimited_options(options)
    bytes = _decompressed_bytes(path, compression)
    _validated_text(bytes)
    records = _physical_records(bytes; empty_allowed=false)
    header = String.(_parse_fields(first(records), delimiter))
    header == names || throw(DecodeError("artifact header does not match the recipe"))
    logical_values = [Any[] for _ in names]
    valid = [BitVector() for _ in names]
    native = [Any[] for _ in names]
    for record in @view records[2:end]
        fields = _parse_fields(record, delimiter)
        length(fields) == length(names) || throw(DecodeError("record has the wrong field count"))
        for index in eachindex(fields)
            value = String(fields[index])
            if value in missing_values
                zero_value = types[index] == "float64" ? 0.0 :
                             types[index] == "int64" ? Int64(0) :
                             types[index] == "bool" ? false : ""
                push!(logical_values[index], zero_value)
                push!(native[index], missing)
                push!(valid[index], false)
            else
                parsed = _parse_delimited_value(value, types[index])
                push!(logical_values[index], parsed)
                push!(native[index], parsed)
                push!(valid[index], true)
            end
        end
    end
    typed_logical = AbstractVector[]
    typed_native = AbstractVector[]
    for index in eachindex(names)
        T = types[index] == "float64" ? Float64 :
            types[index] == "int64" ? Int64 :
            types[index] == "bool" ? Bool : String
        push!(typed_logical, T.(logical_values[index]))
        converted = Vector{Union{Missing,T}}(undef, length(native[index]))
        converted .= native[index]
        push!(typed_native, converted)
    end
    components = Tuple(
        LogicalVector(names[index], types[index], typed_logical[index], valid[index]) for
        index in eachindex(names)
    )
    data = DataFrame([Symbol(names[index]) => typed_native[index] for index in eachindex(names)])
    return Decoded(data, components)
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

function _parse_svm_number(value::AbstractString, logical_type::String)
    pattern = logical_type == "int64" ? _SVM_INT_PATTERN : _SVM_FLOAT_PATTERN
    occursin(pattern, value) || throw(DecodeError("invalid $logical_type value '$value'"))
    parsed = logical_type == "int64" ? tryparse(Int64, value) : tryparse(Float64, value)
    parsed !== nothing || throw(DecodeError("$logical_type value is out of range"))
    parsed isa Float64 && !isfinite(parsed) && throw(DecodeError("float64 value is not finite"))
    return parsed
end

function decode_libsvm(path, options::AbstractDict; compression="none", prefix="")
    feature_count, label_type, target_name = _validate_libsvm_options(options)
    bytes = _decompressed_bytes(path, compression)
    _validated_text(bytes)
    records = _physical_records(bytes; empty_allowed=true)
    rows = Int[]
    columns = Int[]
    values = Float64[]
    labels_int = Int64[]
    labels_float = Float64[]
    row_offsets = Int[0]
    canonical_columns = Int[]
    for (row, record) in enumerate(records)
        isempty(record) && throw(DecodeError("blank LIBSVM records are invalid"))
        first(record) in (0x20, 0x09) && throw(DecodeError("leading whitespace is invalid"))
        line = String(record)
        line = rstrip(character -> character == ' ' || character == '\t', line)
        tokens = split(line, r"[ \t]+"; keepempty=false)
        isempty(tokens) && throw(DecodeError("LIBSVM record has no label"))
        label = _parse_svm_number(tokens[1], label_type)
        label_type == "int64" ? push!(labels_int, label) : push!(labels_float, label)
        previous = 0
        for token in @view tokens[2:end]
            parts = split(token, ':'; keepempty=true)
            length(parts) == 2 || throw(DecodeError("invalid LIBSVM feature token"))
            occursin(_INDEX_PATTERN, parts[1]) || throw(DecodeError("invalid feature index"))
            column = tryparse(Int, parts[1])
            column !== nothing && 1 <= column <= feature_count ||
                throw(DecodeError("feature index is out of range"))
            column > previous || throw(DecodeError("feature indices must strictly increase"))
            value = _parse_svm_number(parts[2], "float64")
            value != 0.0 || throw(DecodeError("stored sparse zero is invalid"))
            push!(rows, row)
            push!(columns, column)
            push!(canonical_columns, column - 1)
            push!(values, value)
            previous = column
        end
        push!(row_offsets, length(values))
    end
    response = label_type == "int64" ? labels_int : labels_float
    features = if feature_count <= 10_000_000
        sparse(rows, columns, values, length(records), feature_count)
    else
        CSRMatrix(
            length(records),
            feature_count,
            row_offsets,
            canonical_columns,
            values,
        )
    end
    feature_component = LogicalSparseMatrix(
        prefix * "features",
        length(records),
        feature_count,
        row_offsets,
        canonical_columns,
        values,
    )
    response_component = LogicalVector(
        prefix * target_name,
        label_type,
        response,
        trues(length(response)),
    )
    return Decoded(SparseDataset(features, response), (feature_component, response_component))
end

function decode_libsvm_split(
    train_path,
    test_path,
    options::AbstractDict;
    train_compression="none",
    test_compression="none",
)
    train = decode_libsvm(train_path, options; compression=train_compression, prefix="train_")
    test = decode_libsvm(test_path, options; compression=test_compression, prefix="test_")
    data = SparseDatasetSplit(train.data, test.data)
    return Decoded(data, (train.components..., test.components...))
end
