function _citation_metadata(dataset)
    provenance = _require_object(get(dataset, "provenance", Dict{String,Any}()), "provenance")
    haskey(provenance, "citation") && haskey(provenance, "citations") &&
        throw(UnsupportedRegistryError("provenance cannot contain citation and citations"))
    if get(dataset, "schema_version", nothing) == 1 &&
       (haskey(provenance, "citations") || haskey(provenance, "citation_instructions"))
        throw(UnsupportedRegistryError("multiple citations require manifest schema 2"))
    end
    function nonempty(value, field)
        text = _require_string(value, field)
        isempty(text) && throw(UnsupportedRegistryError("$field must not be empty"))
        return text
    end
    instructions = haskey(provenance, "citation_instructions") ?
        nonempty(provenance["citation_instructions"], "citation instructions") : nothing
    if haskey(provenance, "citation")
        return [Dict{String,Any}("citation" => nonempty(provenance["citation"], "citation"))], instructions
    end
    records = Dict{String,Any}[]
    for raw in _require_array(get(provenance, "citations", Any[]), "citations")
        record = Dict{String,Any}(_require_object(raw, "citation record"))
        isempty(setdiff(keys(record), ("citation", "role", "note", "recommended"))) ||
            throw(UnsupportedRegistryError("unknown citation record field"))
        nonempty(get(record, "citation", nothing), "citation")
        if haskey(record, "role")
            nonempty(record["role"], "citation role") in ("dataset", "paper", "collection") ||
                throw(UnsupportedRegistryError("unsupported citation role"))
        end
        haskey(record, "note") && nonempty(record["note"], "citation note")
        if haskey(record, "recommended") && !(record["recommended"] isa Bool)
            throw(UnsupportedRegistryError("citation recommended must be a boolean"))
        end
        push!(records, record)
    end
    return records, instructions
end

"""
Get curated citations without retrieving dataset artifacts.

Return text by default, or reference records with `format="records"`. Select
references explicitly marked as recommended by upstream. If no recommendation
flags are recorded, return all references and explain the unknown recommendation
in text output. Set `include_all=true` to return every reference. Records retain
optional roles, notes, and recommendation flags. Full records and upstream
instructions are available through `data_info()` and fetch metadata.

Dataset references, registry selection, and offline behavior match `data_info()`.
"""
function cite_data(
    name;
    source=nothing,
    version=nothing,
    registry=nothing,
    cache_dir=nothing,
    offline=false,
    include_all=false,
    format="text",
)
    include_all isa Bool || throw(ArgumentError("include_all must be a boolean"))
    format in ("text", "records") || throw(ArgumentError("format must be 'text' or 'records'"))
    info = data_info(name; source, version, registry, cache_dir, offline)
    records = info.citations
    known = any(record -> haskey(record, "recommended"), records)
    selected = include_all || !known ? records :
        filter(record -> get(record, "recommended", nothing) === true, records)
    format == "records" && return selected
    paragraphs = info.citation_instructions === nothing ? String[] : [info.citation_instructions]
    if isempty(records)
        push!(paragraphs, "No citation metadata is recorded.")
    elseif !known
        push!(paragraphs, "No upstream citation recommendation is recorded.")
    elseif isempty(selected)
        push!(paragraphs, "No references are marked as recommended.")
    end
    for record in selected
        role = haskey(record, "role") ? "[$(record["role"])] " : ""
        text = role * record["citation"]
        haskey(record, "note") && (text *= "\n" * record["note"])
        push!(paragraphs, text)
    end
    return join(paragraphs, "\n\n")
end
