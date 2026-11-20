const _HIF_TABLES = ("nodes", "hyperedges", "incidences")

_graph_error(message) = throw(UnsupportedDecoderError(message))

function _graph_fields(value, names)
    value isa AbstractDict && Set(keys(value)) == Set(names) ||
        _graph_error("invalid graph recipe fields")
    return value
end

function _hif_table(value, reserved)
    options = _graph_fields(value, ("weight", "attributes"))
    weight, attributes = options["weight"], options["attributes"]
    weight isa Bool && attributes isa AbstractVector || _graph_error("invalid HIF columns")
    names = Set(reserved)
    weight && push!(names, "weight")
    columns = Tuple{String,String}[]
    for attribute in attributes
        column = _graph_fields(attribute, ("name", "type"))
        name, kind = column["name"], column["type"]
        name isa String && !isempty(name) && !(name in names) &&
            kind in ("int64", "string", "float64", "bool") ||
            _graph_error("invalid or duplicate HIF attribute")
        push!(names, name)
        push!(columns, (name, kind))
    end
    return (columns, weight)
end

function _graph_setup(dataset, representation, decoder)
    graph = decoder == "graph-tables"
    modality = graph ? "graph" : "hypergraph"
    get(dataset, "schema_version", nothing) === 8 && get(dataset, "modality", nothing) == modality &&
        get(representation, "decoder_version", nothing) === 1 ||
        _graph_error("graph and HIF recipes require manifest schema 8")
    roles = graph ? ("nodes", "edges") : ("data",)
    artifacts = _representation_artifacts(dataset, representation, roles)
    compressions = [get(artifact, "compression", nothing) for artifact in artifacts]
    all(c -> c in ("none", "gzip", "bzip2"), compressions) ||
        _graph_error("unsupported graph artifact compression")
    fields = graph ? roles : ("node_id", "edge_id", _HIF_TABLES...)
    options = _graph_fields(get(representation, "options", nothing), ("directed", fields...))
    directed = options["directed"]
    directed isa Bool || _graph_error("directed must be a boolean")
    if graph
        for (role, artifact) in zip(roles, artifacts)
            table = options[role]
            table isa AbstractDict || _graph_error("expected graph table options")
            delimiter, _, _, _ = _validate_delimited_options(table)
            format = get(artifact, "format", nothing)
            ((format == "csv" && delimiter == UInt8(',')) ||
                (format == "tsv" && delimiter == UInt8('\t'))) ||
                _graph_error("graph table format and delimiter disagree")
        end
    else
        get(only(artifacts), "format", nothing) == "hif" &&
            all(key -> options[key] in ("int64", "string"), ("node_id", "edge_id")) ||
            _graph_error("invalid HIF artifact format or ID type")
        options = copy(options)
        for (role, reserved) in zip(_HIF_TABLES, (("id",), ("id",), ("node", "edge", "direction")))
            options[role] = _hif_table(options[role], reserved)
        end
    end
    _native_symbol(:dm_abi_version)
    symbol = graph ? :dm_assemble_graph : :dm_decode_hif
    Libdl.dlsym_e(_NATIVE_LIBRARY[], symbol) != C_NULL ||
        _graph_error("graph and HIF decoding require an updated native artifact")
    return (; representation, decoder, artifacts, options, compressions)
end

function _decode_graph(setup, paths)
    options = setup.options
    directed = options["directed"]
    if setup.decoder == "graph-tables"
        nodes, edges = (
            decode_delimited(path, options[role]; compression)
            for (role, path, compression) in zip(("nodes", "edges"), paths, setup.compressions)
        )
        components = _native_assemble_graph(directed, nodes.components, edges.components)
        return Decoded(GraphDataset(directed, nodes.data, edges.data), components)
    end
    components = _native_decode_hif(only(paths), only(setup.compressions),
        directed, options["node_id"], options["edge_id"],
        options["nodes"], options["hyperedges"], options["incidences"])
    nodes, hyperedges, incidences = (
        _decoded_dataframe([
            _rename_component(c, chop(c.name; head=length(role)+1, tail=0))
            for c in components if startswith(c.name, role * "/")
        ])
        for role in _HIF_TABLES
    )
    return Decoded(HypergraphDataset(directed, nodes, hyperedges, incidences), components)
end
