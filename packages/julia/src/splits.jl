_split_component_name(split, component) = join(
    (replace(s, "~" => "~0", "/" => "~1") for s in (split, component)), "/")

function _split_recipes(representation)
    fail(message) = throw(UnsupportedDecoderError(message))
    get(representation, "decoder_version", nothing) === 1 || fail("unsupported named-splits version")
    options = get(representation, "options", nothing)
    options isa AbstractDict && Set(keys(options)) == Set(["splits"]) ||
        fail("named-splits options must contain exactly splits")
    splits = options["splits"]
    splits isa AbstractVector && !isempty(splits) || fail("splits must be a nonempty array")
    names = String[]
    for split in splits
        split isa AbstractDict && Set(keys(split)) == Set(["name", "decoder", "decoder_version", "options"]) ||
            fail("invalid split recipe fields")
        name = split["name"]
        name isa String && !isempty(name) && !(name in names) ||
            fail("split names must be nonempty and unique")
        push!(names, name)
        typeof(split["decoder_version"]) === Int && split["decoder_version"] in (split["decoder"] == "libsvm" ? (1, 2) : (1,)) && split["decoder"] in ("delimited-text", "libsvm") &&
            split["options"] isa AbstractDict || fail("unsupported split decoder recipe")
    end
    inputs = get(representation, "inputs", nothing)
    inputs isa AbstractDict && Set(keys(inputs)) == Set(names) ||
        fail("input names must match the declared split names")
    return splits
end

_rename_component(c::LogicalVector, name) = LogicalVector(name, c.logical_type, c.values, c.valid)
_rename_component(c::LogicalSparseMatrix, name) = LogicalSparseMatrix(
    name, c.rows, c.columns, c.row_offsets, c.column_indices, c.values)

function _decode_setup(setup, paths)
    if setup.decoder == "named-splits"
        names = String[]
        data = Dict{String,Union{DataFrame,SparseDataset}}()
        components = LogicalComponent[]
        for (i, child_setup) in enumerate(setup.children)
            child = _decode_setup(child_setup, paths[i:i])
            name = setup.options["splits"][i]["name"]
            push!(names, name)
            data[name] = child.data
            append!(components, [_rename_component(c, _split_component_name(name, c.name)) for c in child.components])
        end
        return Decoded(DatasetSplits(names, data), Tuple(components))
    elseif setup.decoder == "delimited-text"
        return decode_delimited(paths[1], setup.options; compression=setup.compressions[1])
    elseif setup.decoder == "libsvm"
        return decode_libsvm(paths[1], setup.options; compression=setup.compressions[1], decoder_version=setup.representation["decoder_version"])
    end
    return decode_libsvm_split(paths[1], paths[2], setup.options;
        train_compression=setup.compressions[1], test_compression=setup.compressions[2], decoder_version=setup.representation["decoder_version"])
end
