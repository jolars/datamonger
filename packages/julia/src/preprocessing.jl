function _preprocessing_metadata(dataset)
    haskey(dataset, "preprocessing") || return nothing
    fail(message) = throw(UnsupportedRegistryError(message))
    function nonempty(value, field)
        text = _require_string(value, field)
        isempty(text) && fail("$field must not be empty")
        return text
    end
    get(dataset, "schema_version", nothing) in (3, 4) ||
        fail("preprocessing requires manifest schema 3 or 4")
    metadata = _require_object(dataset["preprocessing"], "preprocessing")
    Set(keys(metadata)) == Set(["upstream", "datamonger"]) ||
        fail("preprocessing requires exactly two stages")
    for stage in values(metadata)
        _require_object(stage, "preprocessing stage")
        isempty(setdiff(keys(stage), ("status", "steps", "evidence", "notes"))) ||
            fail("unknown preprocessing stage field")
        status = nonempty(get(stage, "status", nothing), "preprocessing status")
        status in ("unknown", "none", "documented") || fail("unsupported preprocessing status")
        haskey(stage, "notes") && nonempty(stage["notes"], "preprocessing notes")
        status != "unknown" && !haskey(stage, "evidence") &&
            fail("known preprocessing requires evidence")
        if haskey(stage, "evidence")
            evidence = _require_array(stage["evidence"], "preprocessing evidence")
            isempty(evidence) && fail("preprocessing evidence must not be empty")
            for reference in evidence
                nonempty(reference, "preprocessing evidence reference")
            end
        end
        if status != "documented"
            haskey(stage, "steps") && fail("only documented processing has steps")
            continue
        end
        steps = _require_array(get(stage, "steps", nothing), "preprocessing steps")
        isempty(steps) && fail("documented preprocessing requires steps")
        for step in steps
            _require_object(step, "preprocessing step")
            isempty(setdiff(keys(step), ("kind", "description", "parameters"))) ||
                fail("unknown preprocessing step field")
            kind = nonempty(get(step, "kind", nothing), "preprocessing kind")
            occursin(_IDENTIFIER_PATTERN, kind) || fail("invalid preprocessing kind")
            nonempty(get(step, "description", nothing), "preprocessing description")
            if haskey(step, "parameters")
                parameters = _require_object(step["parameters"], "preprocessing parameters")
                for (key, value) in parameters
                    nonempty(key, "preprocessing parameter name")
                    nonempty(value, "preprocessing parameter value")
                end
            end
        end
    end
    return Dict{String,Any}(metadata)
end
