function _require_object(value, field)
    value isa AbstractDict || throw(UnsupportedRegistryError("$field must be an object"))
    return value
end

function _require_array(value, field)
    value isa AbstractVector || throw(UnsupportedRegistryError("$field must be an array"))
    return value
end

function _require_string(value, field)
    value isa String || throw(UnsupportedRegistryError("$field must be a string"))
    return value
end

function _require_integer(value, field)
    value isa Integer && !(value isa Bool) && 0 <= value <= 9007199254740991 ||
        throw(UnsupportedRegistryError("$field must be an exact nonnegative JSON integer"))
    return Int(value)
end

_selected_registry(registry) = registry === nothing ? active_registry() : registry

function _artifacts(dataset)
    return [_require_object(value, "artifact") for value in _require_array(get(dataset, "artifacts", nothing), "artifacts")]
end

function _select_artifact(dataset, artifact_name)
    artifacts = _artifacts(dataset)
    names = [_require_string(get(artifact, "name", nothing), "artifact name") for artifact in artifacts]
    if artifact_name === nothing
        length(artifacts) == 1 ||
            throw(ArtifactSelectionError("artifact name is required; available artifacts: $(join(names, ", "))"))
        return only(artifacts)
    end
    matches = findall(==(artifact_name), names)
    length(matches) == 1 ||
        throw(ArtifactSelectionError("unknown artifact '$artifact_name'; available artifacts: $(join(names, ", "))"))
    return artifacts[only(matches)]
end

function _representation_artifacts(dataset, representation, roles)
    inputs = _require_object(get(representation, "inputs", nothing), "representation inputs")
    Set(String.(keys(inputs))) == Set(roles) ||
        throw(UnsupportedRegistryError("representation inputs must be exactly $(join(roles, ", "))"))
    artifacts = _artifacts(dataset)
    selected = Dict{String,Any}[]
    for role in roles
        name = _require_string(get(inputs, role, nothing), "representation input '$role'")
        matches = [artifact for artifact in artifacts if get(artifact, "name", nothing) == name]
        length(matches) == 1 ||
            throw(UnsupportedRegistryError("representation input refers to unknown artifact '$name'"))
        push!(selected, Dict{String,Any}(only(matches)))
    end
    return selected
end

function _artifact_locations(artifact)
    name = _require_string(get(artifact, "name", nothing), "artifact name")
    distribution = _require_string(get(artifact, "distribution", nothing), "artifact distribution")
    distribution == "metadata-only" &&
        throw(ArtifactUnavailableError("artifact '$name' is metadata-only"))
    distribution in ("mirror", "upstream-only") ||
        throw(UnsupportedRegistryError("artifact '$name' has unsupported distribution"))
    downloads = _require_array(get(artifact, "downloads", nothing), "artifact downloads")
    isempty(downloads) && throw(UnsupportedRegistryError("artifact has no retrieval locations"))
    urls = String[]
    for raw in downloads
        download = _require_object(raw, "artifact download")
        get(download, "kind", nothing) in ("mirror", "upstream") ||
            throw(UnsupportedRegistryError("unsupported artifact download kind"))
        url = _require_string(get(download, "url", nothing), "artifact URL")
        _is_http_url(url) || throw(UnsupportedRegistryError("artifact URL is invalid"))
        push!(urls, url)
    end
    length(unique(urls)) == length(urls) ||
        throw(UnsupportedRegistryError("artifact URLs must be unique"))
    return urls
end

function _retrieve_artifact(artifact, cache_dir, offline)
    urls = _artifact_locations(artifact)
    digest = _require_string(get(artifact, "sha256", nothing), "artifact SHA-256")
    occursin(_SHA256_PATTERN, digest) ||
        throw(UnsupportedRegistryError("artifact SHA-256 is invalid"))
    size = _require_integer(get(artifact, "size", nothing), "artifact size")
    return _retrieve_cached_object(
        cache_dir,
        "objects",
        digest,
        size,
        urls,
        offline,
        ArtifactIntegrityError,
        OfflineError,
        RetrievalLocationsError,
    )
end

"""Retrieve one verified artifact without decoding it."""
function fetch_artifact(
    name;
    source,
    version=nothing,
    artifact=nothing,
    registry=nothing,
    cache_dir=nothing,
    offline=false,
)
    offline isa Bool || throw(ArgumentError("offline must be true or false"))
    cache_dir = datamonger_cache_dir(cache_dir)
    selected = _selected_registry(registry)
    index = _load_registry(selected, cache_dir; offline)
    dataset = _resolve_dataset(index, source, name, version)
    object = _retrieve_artifact(_select_artifact(dataset, artifact), cache_dir, offline)
    try
        return object.path
    finally
        _release_cached(object)
    end
end

function _records(value, field)
    return [Dict{String,Any}(_require_object(record, field)) for record in _require_array(value, field)]
end

function _optional_records(value, field)
    value === nothing && return Dict{String,Any}[]
    return _records(value, field)
end

function _data_info(dataset, registry)
    source = _require_string(get(dataset, "source", nothing), "dataset source")
    name = _require_string(get(dataset, "name", nothing), "dataset name")
    version = _require_string(get(dataset, "version", nothing), "dataset version")
    representation = Dict{String,Any}(
        _require_object(get(dataset, "representation", nothing), "representation"),
    )
    expect = _require_object(get(representation, "expect", nothing), "representation expectation")
    return DataInfo(
        "$source:$name@$version",
        source,
        name,
        version,
        registry.release,
        registry.index_sha256,
        _require_string(get(dataset, "title", nothing), "dataset title"),
        _require_string(get(dataset, "description", nothing), "dataset description"),
        _require_string(get(dataset, "modality", nothing), "dataset modality"),
        Dict{String,Any}(_require_object(get(dataset, "provenance", nothing), "provenance")),
        Dict{String,Any}(_require_object(get(dataset, "license", nothing), "license")),
        [Dict{String,Any}(artifact) for artifact in _artifacts(dataset)],
        representation,
        _records(get(expect, "components", nothing), "expected components"),
        _records(get(expect, "verification", nothing), "verification records"),
        _optional_records(get(dataset, "related", nothing), "related datasets"),
        _optional_records(get(dataset, "tasks", nothing), "tasks"),
    )
end

"""Inspect one resolved dataset without retrieving its artifacts."""
function data_info(
    name;
    source,
    version=nothing,
    registry=nothing,
    cache_dir=nothing,
    offline=false,
)
    offline isa Bool || throw(ArgumentError("offline must be true or false"))
    cache_dir = datamonger_cache_dir(cache_dir)
    selected = _selected_registry(registry)
    index = _load_registry(selected, cache_dir; offline)
    return _data_info(_resolve_dataset(index, source, name, version), selected)
end

"""List every dataset version in the selected immutable registry."""
function list_data(; registry=nothing, cache_dir=nothing, offline=false)
    offline isa Bool || throw(ArgumentError("offline must be true or false"))
    cache_dir = datamonger_cache_dir(cache_dir)
    selected = _selected_registry(registry)
    index = _load_registry(selected, cache_dir; offline)
    results = DataInfo[]
    for raw in index["datasets"]
        dataset = _require_object(raw, "dataset")
        source = _require_string(get(dataset, "source", nothing), "dataset source")
        name = _require_string(get(dataset, "name", nothing), "dataset name")
        version = _require_string(get(dataset, "version", nothing), "dataset version")
        push!(results, _data_info(_resolve_dataset(index, source, name, version), selected))
    end
    return results
end

function _validate_representation(dataset)
    representation = _require_object(get(dataset, "representation", nothing), "representation")
    decoder = get(representation, "decoder", nothing)
    decoder_version = get(representation, "decoder_version", nothing)
    decoder_version isa Integer && !(decoder_version isa Bool) && decoder_version == 1 &&
        decoder in ("delimited-text", "libsvm", "libsvm-split") ||
        throw(UnsupportedDecoderError(
            "Julia supports delimited-text, LIBSVM, and LIBSVM split version 1",
        ))
    roles = decoder == "libsvm-split" ? ["train", "test"] : ["data"]
    artifacts = _representation_artifacts(dataset, representation, roles)
    options = _require_object(get(representation, "options", nothing), "representation options")
    compressions = String[]
    formats = String[]
    for artifact in artifacts
        compression = _require_string(get(artifact, "compression", nothing), "artifact compression")
        compression in ("none", "gzip", "bzip2") ||
            throw(UnsupportedDecoderError("unsupported artifact compression"))
        push!(compressions, compression)
        push!(formats, _require_string(get(artifact, "format", nothing), "artifact format"))
    end
    if decoder == "delimited-text"
        only(formats) in ("csv", "tsv") ||
            throw(UnsupportedDecoderError("delimited-text requires CSV or TSV"))
        expected_delimiter = only(formats) == "csv" ? "," : "\t"
        get(options, "delimiter", nothing) == expected_delimiter ||
            throw(UnsupportedDecoderError("artifact format and delimiter disagree"))
    else
        all(format -> format in ("libsvm", "svmlight"), formats) ||
            throw(UnsupportedDecoderError("LIBSVM requires LIBSVM or SVMLight artifacts"))
    end
    return (representation=representation, decoder=decoder, artifacts=artifacts, options=options, compressions=compressions)
end

function _component_matches(component::LogicalVector, expectation)
    return get(expectation, "kind", nothing) == "vector" &&
           get(expectation, "name", nothing) == component.name &&
           get(expectation, "type", nothing) == component.logical_type &&
           get(expectation, "length", nothing) == length(component.values)
end

function _component_matches(component::LogicalSparseMatrix, expectation)
    return get(expectation, "kind", nothing) == "sparse_matrix" &&
           get(expectation, "name", nothing) == component.name &&
           get(expectation, "type", "float64") == "float64" &&
           get(expectation, "rows", nothing) == component.rows &&
           get(expectation, "columns", nothing) == component.columns
end

function _validate_components(components, expected)
    expected = _require_array(expected, "expected components")
    length(components) == length(expected) ||
        throw(DecodedIntegrityError("decoded component count does not match expectation"))
    for (component, raw) in zip(components, expected)
        expectation = _require_object(raw, "component expectation")
        _component_matches(component, expectation) ||
            throw(DecodedIntegrityError("decoded component '$(component.name)' does not match expectation"))
    end
end

function _verification_record(index, dataset, expect)
    identity = Dict(
        "source" => dataset["source"],
        "name" => dataset["name"],
        "version" => dataset["version"],
    )
    revoked = Any[]
    for raw in _require_array(get(index, "errata", Any[]), "registry errata")
        erratum = _require_object(raw, "registry erratum")
        get(erratum, "dataset", nothing) == identity || continue
        target = _require_object(get(erratum, "target", nothing), "erratum target")
        get(target, "kind", nothing) == "verification" || continue
        push!(revoked, _require_object(get(erratum, "original", nothing), "erratum original"))
    end
    records = _require_array(get(expect, "verification", nothing), "verification records")
    for raw in Iterators.reverse(records)
        record = _require_object(raw, "verification record")
        if get(record, "canonical_form", nothing) == 1 &&
           get(record, "algorithm", nothing) == "sha256" &&
           !any(original -> original == record, revoked)
            return record
        end
    end
    throw(UnsupportedDecoderError("no supported decoded-verification record"))
end

"""Resolve, retrieve, verify, and decode one registered dataset."""
function fetch_data(
    name;
    source,
    version=nothing,
    registry=nothing,
    cache_dir=nothing,
    offline=false,
    verify_decoded=true,
    return_info=false,
)
    all(value -> value isa Bool, (offline, verify_decoded, return_info)) ||
        throw(ArgumentError("offline, verify_decoded, and return_info must be booleans"))
    cache_dir = datamonger_cache_dir(cache_dir)
    selected = _selected_registry(registry)
    index = _load_registry(selected, cache_dir; offline)
    dataset = _resolve_dataset(index, source, name, version)
    setup = _validate_representation(dataset)
    objects = CachedObject[]
    try
        for artifact in setup.artifacts
            push!(objects, _retrieve_artifact(artifact, cache_dir, offline))
        end
        paths = [object.path for object in objects]
        decoded = if setup.decoder == "delimited-text"
            decode_delimited(paths[1], setup.options; compression=setup.compressions[1])
        elseif setup.decoder == "libsvm"
            decode_libsvm(paths[1], setup.options; compression=setup.compressions[1])
        else
            decode_libsvm_split(
                paths[1],
                paths[2],
                setup.options;
                train_compression=setup.compressions[1],
                test_compression=setup.compressions[2],
            )
        end

        verification = :artifact
        canonical_form = nothing
        canonical_digest = nothing
        if verify_decoded
            expect = _require_object(get(setup.representation, "expect", nothing), "representation expectation")
            _validate_components(decoded.components, get(expect, "components", nothing))
            record = _verification_record(index, dataset, expect)
            canonical_form = _require_integer(get(record, "canonical_form", nothing), "canonical form")
            expected_digest = _require_string(get(record, "digest", nothing), "canonical digest")
            occursin(_SHA256_PATTERN, expected_digest) ||
                throw(UnsupportedRegistryError("canonical digest is invalid"))
            canonical_digest = canonical_sha256(decoded.components)
            canonical_digest == expected_digest || throw(DecodedIntegrityError(
                "decoded SHA-256 mismatch: expected $expected_digest, received $canonical_digest",
            ))
            verification = :decoded
        end

        artifact_digests = Dict(
            _require_string(artifact["name"], "artifact name") =>
                _require_string(artifact["sha256"], "artifact digest") for artifact in setup.artifacts
        )
        resolved_source = _require_string(dataset["source"], "dataset source")
        resolved_name = _require_string(dataset["name"], "dataset name")
        resolved_version = _require_string(dataset["version"], "dataset version")
        info = FetchInfo(
            "$resolved_source:$resolved_name@$resolved_version",
            selected.release,
            selected.index_sha256,
            artifact_digests,
            verification,
            canonical_form,
            canonical_digest,
        )
        return return_info ? FetchResult(decoded.data, info) : decoded.data
    finally
        for object in objects
            _release_cached(object)
        end
    end
end
