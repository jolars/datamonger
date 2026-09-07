const _IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9._-]*$"
const _VERSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._+-]*$"
const _RELEASE_PATTERN = _IDENTIFIER_PATTERN
const DEFAULT_CATALOG_URL =
    "https://raw.githubusercontent.com/jolars/datamonger/main/registry/catalog.json"

function _is_http_url(value; https_only=false)
    value isa String || return false
    occursin(r"\s", value) && return false
    uri = try
        HTTP.URI(value)
    catch
        return false
    end
    allowed = https_only ? ("https",) : ("http", "https")
    return uri.scheme in allowed && !isempty(uri.host)
end

function validate_registry_selector(registry::Registry)
    registry.schema_version == 1 ||
        throw(UnsupportedRegistryError("unsupported selector schema $(registry.schema_version)"))
    occursin(_RELEASE_PATTERN, registry.release) ||
        throw(RegistryRetrievalError("registry release identifier is invalid"))
    occursin(_SHA256_PATTERN, registry.index_sha256) ||
        throw(RegistryIntegrityError("registry SHA-256 must contain 64 lowercase hexadecimal digits"))
    _is_http_url(registry.index_url) ||
        throw(RegistryRetrievalError("registry index URL must be absolute HTTP(S)"))
    return nothing
end

"""Construct and validate a revision-1 strong registry selector."""
registry_selector(release, index_sha256, index_url; schema_version=1) =
    Registry(release, index_sha256, index_url, schema_version)

const BUNDLED_REGISTRY = Registry(
    "proof-0001",
    "98cdbc7c8c795dcd021775de4c955c2442e6e1f2d7911e4c53b72327d90f6578",
    "https://github.com/jolars/datamonger/releases/download/registry-proof-0001/index.json",
)

const _SESSION_REGISTRY = Ref{Union{Nothing,Registry}}(nothing)

function _parse_json_object(bytes, description, error_type=RegistryRetrievalError)
    isvalid(String, bytes) || throw(error_type("$description is not valid UTF-8"))
    parsed = try
        JSON3.read(bytes, Dict{String,Any})
    catch error
        throw(error_type("$description is invalid JSON: $(sprint(showerror, error))"))
    end
    return parsed
end

function _selector_from_object(object::AbstractDict)
    Set(String.(keys(object))) == Set(["schema_version", "release", "index_sha256", "index_url"]) ||
        throw(RegistryRetrievalError("selector has unexpected or missing fields"))
    schema = get(object, "schema_version", nothing)
    schema isa Integer && !(schema isa Bool) ||
        throw(UnsupportedRegistryError("selector schema version must be an integer"))
    all(field -> get(object, field, nothing) isa String, ["release", "index_sha256", "index_url"]) ||
        throw(RegistryRetrievalError("selector fields must be strings"))
    return Registry(
        object["release"],
        object["index_sha256"],
        object["index_url"],
        object["schema_version"],
    )
end

"""Discover a strong selector by release name through an HTTPS catalog."""
function resolve_registry(release; catalog_url=DEFAULT_CATALOG_URL)
    release isa String && occursin(_RELEASE_PATTERN, release) ||
        throw(RegistryRetrievalError("registry release identifier is invalid"))
    _is_http_url(catalog_url; https_only=true) ||
        throw(RegistryRetrievalError("registry catalog URL must be absolute HTTPS"))
    response = try
        HTTP.request(
            "GET",
            catalog_url,
            ["Accept-Encoding" => "identity"];
            decompress=false,
            status_exception=false,
            redirect=true,
        )
    catch error
        throw(RegistryRetrievalError("cannot retrieve registry catalog: $(sprint(showerror, error))"))
    end
    200 <= response.status < 300 ||
        throw(RegistryRetrievalError("registry catalog returned HTTP $(response.status)"))
    try
        _validate_redirects(response)
    catch error
        throw(RegistryRetrievalError(sprint(showerror, error)))
    end
    _is_http_url(string(response.request_url); https_only=true) ||
        throw(RegistryRetrievalError("catalog redirected to a non-HTTPS URL"))
    body = try
        _decoded_http_body(response, catalog_url)
    catch error
        throw(RegistryRetrievalError(sprint(showerror, error)))
    end
    catalog = _parse_json_object(body, "registry catalog")
    schema = get(catalog, "schema_version", nothing)
    schema isa Integer && !(schema isa Bool) && schema == 1 ||
        throw(UnsupportedRegistryError("unsupported registry catalog schema"))
    Set(String.(keys(catalog))) == Set(["schema_version", "releases"]) ||
        throw(RegistryRetrievalError("registry catalog has unexpected fields"))
    releases = get(catalog, "releases", nothing)
    releases isa AbstractVector || throw(RegistryRetrievalError("catalog releases must be an array"))
    found = Registry[]
    seen = Set{String}()
    for raw in releases
        raw isa AbstractDict || throw(RegistryRetrievalError("catalog selector must be an object"))
        selected = _selector_from_object(raw)
        selected.release in seen && throw(RegistryRetrievalError("catalog contains duplicate releases"))
        push!(seen, selected.release)
        selected.release == release && push!(found, selected)
    end
    length(found) == 1 || throw(RegistryRetrievalError("unknown registry release '$release'"))
    return only(found)
end

"""Set a session registry selector, or clear it with `nothing`."""
function set_registry!(registry::Union{Nothing,Registry})
    _SESSION_REGISTRY[] = registry
    return registry
end

"""Alias for [`set_registry!`](@ref)."""
set_registry(registry::Union{Nothing,Registry}) = set_registry!(registry)

function _project_registry(project_dir)
    current = abspath(project_dir)
    while true
        selector_path = joinpath(current, ".datamonger", "selector.json")
        if ispath(selector_path)
            isfile(selector_path) || throw(RegistryRetrievalError("project selector is not a file"))
            bytes = try
                read(selector_path)
            catch error
                throw(RegistryRetrievalError("cannot read project selector: $(sprint(showerror, error))"))
            end
            return _selector_from_object(_parse_json_object(bytes, "project selector"))
        end
        parent = dirname(current)
        parent == current && return nothing
        current = parent
    end
end

"""Return the session, nearest-project, or bundled selector in precedence order."""
function active_registry(; project_dir=pwd())
    _SESSION_REGISTRY[] !== nothing && return _SESSION_REGISTRY[]
    project = _project_registry(project_dir)
    return project === nothing ? BUNDLED_REGISTRY : project
end

function _load_registry(registry::Registry, cache_dir; offline=false)
    validate_registry_selector(registry)
    bytes = if registry.release == BUNDLED_REGISTRY.release &&
               registry.index_sha256 == BUNDLED_REGISTRY.index_sha256
        contents = try
            read(joinpath(@__DIR__, "data", "index.json"))
        catch error
            throw(RegistryRetrievalError("cannot read bundled registry: $(sprint(showerror, error))"))
        end
        actual = bytes2hex(sha256(contents))
        actual == registry.index_sha256 ||
            throw(RegistryIntegrityError("bundled registry SHA-256 mismatch"))
        contents
    else
        object = _retrieve_cached_object(
            cache_dir,
            "registries",
            registry.index_sha256,
            nothing,
            [registry.index_url],
            offline,
            RegistryIntegrityError,
            RegistryOfflineError,
            RegistryRetrievalError,
        )
        try
            read(object.path)
        catch error
            throw(RegistryRetrievalError("cannot read registry index: $(sprint(showerror, error))"))
        finally
            _release_cached(object)
        end
    end
    index = _parse_json_object(bytes, "registry index", UnsupportedRegistryError)
    schema = get(index, "schema_version", nothing)
    schema isa Integer && !(schema isa Bool) && schema == 1 ||
        throw(UnsupportedRegistryError("unsupported registry schema"))
    get(index, "release", nothing) == registry.release ||
        throw(RegistryReleaseError("selected and embedded registry releases disagree"))
    get(index, "datasets", nothing) isa AbstractVector ||
        throw(UnsupportedRegistryError("registry datasets must be an array"))
    get(index, "defaults", nothing) isa AbstractVector ||
        throw(UnsupportedRegistryError("registry defaults must be an array"))
    return index
end

function _resolve_dataset(index::AbstractDict, source, name, version)
    source isa String && name isa String &&
        occursin(_IDENTIFIER_PATTERN, source) && occursin(_IDENTIFIER_PATTERN, name) &&
        (version === nothing || version isa String && occursin(_VERSION_PATTERN, version)) ||
        throw(UnknownDatasetError("invalid or unknown dataset"))
    resolved = version
    if resolved === nothing
        matches = [
            record for record in index["defaults"] if record isa AbstractDict &&
            get(record, "source", nothing) == source && get(record, "name", nothing) == name
        ]
        length(matches) == 1 || throw(UnknownDatasetError("unknown or ambiguous dataset $source:$name"))
        candidate = get(only(matches), "version", nothing)
        candidate isa String || throw(UnsupportedRegistryError("default version must be a string"))
        resolved = candidate
    end
    matches = [
        record for record in index["datasets"] if record isa AbstractDict &&
        get(record, "source", nothing) == source && get(record, "name", nothing) == name &&
        get(record, "version", nothing) == resolved
    ]
    length(matches) == 1 || throw(UnknownDatasetError("unknown dataset $source:$name@$resolved"))
    dataset = only(matches)
    schema = get(dataset, "schema_version", nothing)
    schema isa Integer && !(schema isa Bool) && schema == 1 ||
        throw(UnsupportedRegistryError("unsupported dataset schema"))
    return dataset
end
