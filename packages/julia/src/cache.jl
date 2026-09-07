const _CACHE_NAMESPACES = Set(["objects", "registries"])
const _SHA256_PATTERN = r"^[0-9a-f]{64}$"
const _DATASET_ID_PATTERN =
    r"^[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9._+-]*$"
const _LOCK_SH = 1
const _LOCK_EX = 2
const _LOCK_NB = 4
const _LOCK_UN = 8

mutable struct CacheLease
    handle::Any
    path::String
    pidfile::Bool
end

struct CachedObject
    path::String
    lease::CacheLease
end

"""Return the Julia client's private platform cache path without creating it."""
function default_cache_dir()
    base = if Sys.iswindows()
        get(ENV, "LOCALAPPDATA", first(Base.DEPOT_PATH))
    elseif Sys.isapple()
        joinpath(homedir(), "Library", "Caches")
    else
        get(ENV, "XDG_CACHE_HOME", joinpath(homedir(), ".cache"))
    end
    return abspath(joinpath(base, "datamonger", "julia"))
end

"""Select an explicit cache path or the private platform default."""
function datamonger_cache_dir(cache_dir=nothing)
    return cache_dir === nothing ? default_cache_dir() : abspath(cache_dir)
end

function _lease_path(cache_dir, namespace, digest; publication=false)
    namespace in _CACHE_NAMESPACES || throw(CacheError("unsupported cache namespace '$namespace'"))
    occursin(_SHA256_PATTERN, digest) || throw(CacheError("invalid cache digest '$digest'"))
    suffix = publication ? ".publish.lock" : ".lock"
    return joinpath(cache_dir, ".leases", namespace, "sha256", digest * suffix)
end

function _acquire_lease(path; exclusive, blocking=true)
    try
        mkpath(dirname(path))
    catch error
        throw(CacheError("cannot create cache lease directory: $(sprint(showerror, error))"))
    end
    if Sys.iswindows()
        handle = try
            if blocking
                FileWatching.Pidfile.mkpidlock(path; stale_age=60, refresh=30)
            else
                FileWatching.Pidfile.trymkpidlock(path; stale_age=60, refresh=30)
            end
        catch error
            throw(CacheError("cannot acquire cache lease '$path': $(sprint(showerror, error))"))
        end
        handle === false && return nothing
        return CacheLease(handle, path, true)
    end
    io = try
        open(path, "a+")
    catch error
        throw(CacheError("cannot open cache lease '$path': $(sprint(showerror, error))"))
    end
    operation = exclusive ? _LOCK_EX : _LOCK_SH
    !blocking && (operation |= _LOCK_NB)
    while true
        result = ccall(:flock, Cint, (Cint, Cint), Base.fd(io), operation)
        result == 0 && return CacheLease(io, path, false)
        code = Base.Libc.errno()
        code == Base.Libc.EINTR && continue
        if !blocking && code == Base.Libc.EAGAIN
            close(io)
            return nothing
        end
        close(io)
        throw(CacheError("cannot acquire cache lease '$path': errno $code"))
    end
end

function _release_lease(lease::CacheLease)
    if lease.pidfile
        try
            close(lease.handle)
        catch error
            throw(CacheError("cannot release cache lease '$(lease.path)': $(sprint(showerror, error))"))
        end
        return nothing
    end
    isopen(lease.handle) || return nothing
    result = ccall(:flock, Cint, (Cint, Cint), Base.fd(lease.handle), _LOCK_UN)
    close(lease.handle)
    result == 0 || throw(CacheError("cannot release cache lease '$(lease.path)'"))
    return nothing
end

function _with_lease(f, path; exclusive, blocking=true)
    lease = _acquire_lease(path; exclusive, blocking)
    lease === nothing && return f(nothing)
    try
        return f(lease)
    finally
        _release_lease(lease)
    end
end

function _object_path(cache_dir, namespace, digest)
    namespace in _CACHE_NAMESPACES || throw(CacheError("unsupported cache namespace '$namespace'"))
    occursin(_SHA256_PATTERN, digest) || throw(CacheError("invalid cache digest '$digest'"))
    return joinpath(cache_dir, namespace, "sha256", digest)
end

function _file_digest_and_size(path)
    context = SHA.SHA2_256_CTX()
    count = Int64(0)
    try
        open(path, "r") do io
            buffer = Vector{UInt8}(undef, 1024 * 1024)
            while !eof(io)
                amount = readbytes!(io, buffer)
                amount == 0 && break
                SHA.update!(context, @view buffer[1:amount])
                count += amount
            end
        end
    catch error
        throw(CacheError("cannot read cache object '$path': $(sprint(showerror, error))"))
    end
    return bytes2hex(SHA.digest!(context)), count
end

function _object_matches(path, digest, size)
    isfile(path) || return false
    actual_digest, actual_size = _file_digest_and_size(path)
    return actual_digest == digest && (size === nothing || actual_size == size)
end

function _header_values(response, name)
    return String.(HTTP.headers(response, name))
end

function _validate_redirects(response)
    current = response.previous
    while current !== nothing
        locations = _header_values(current, "Location")
        length(locations) == 1 && _is_http_url(only(locations)) ||
            throw(RetrievalLocationsError("redirect target must be an absolute HTTP(S) URL"))
        current = current.previous
    end
    return nothing
end

function _comma_tokens(values)
    return [strip(token) for value in values for token in split(value, ',')]
end

function _validate_transfer_headers(response, encoded_size, url)
    transfer = lowercase.(_comma_tokens(_header_values(response, "Transfer-Encoding")))
    !isempty(transfer) && transfer != ["chunked"] &&
        throw(RetrievalLocationsError("unsupported HTTP transfer coding from $url"))
    lengths = _comma_tokens(_header_values(response, "Content-Length"))
    if !isempty(lengths)
        all(value -> occursin(r"^[0-9]+$", value), lengths) ||
            throw(RetrievalLocationsError("malformed HTTP Content-Length from $url"))
        parsed = unique(parse.(Int64, lengths))
        length(parsed) == 1 ||
            throw(RetrievalLocationsError("conflicting HTTP Content-Length values from $url"))
        isempty(transfer) && only(parsed) != encoded_size &&
            throw(RetrievalLocationsError("truncated HTTP response from $url"))
    end
end

function _content_coding(response, url)
    tokens = _comma_tokens(_header_values(response, "Content-Encoding"))
    all(token -> occursin(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$", token), tokens) ||
        throw(RetrievalLocationsError("malformed HTTP content coding from $url"))
    non_identity = [lowercase(token) for token in tokens if lowercase(token) != "identity"]
    length(non_identity) <= 1 ||
        throw(RetrievalLocationsError("multiple HTTP content codings from $url"))
    isempty(non_identity) && return nothing
    only(non_identity) in ("gzip", "x-gzip") ||
        throw(RetrievalLocationsError("unsupported HTTP content coding from $url"))
    return only(non_identity)
end

function _copy_and_hash(source, destination; gzip=false, strict_stream=false)
    context = SHA.SHA2_256_CTX()
    count = Int64(0)
    source_stream = source
    transcoded = nothing
    wrapped = nothing
    if gzip
        wrapped = strict_stream ? TranscodingStreams.NoopStream(source) : source
        transcoded = GzipDecompressorStream(
            wrapped;
            gziponly=true,
            stop_on_end=strict_stream,
        )
        source_stream = transcoded
    end
    try
        buffer = Vector{UInt8}(undef, 1024 * 1024)
        while !eof(source_stream)
            amount = readbytes!(source_stream, buffer)
            amount == 0 && break
            write(destination, @view buffer[1:amount])
            SHA.update!(context, @view buffer[1:amount])
            count += amount
        end
        if strict_stream && gzip
            eof(wrapped) || throw(RetrievalLocationsError("trailing or concatenated HTTP gzip content"))
        end
    catch error
        error isa DatamongerError && rethrow()
        throw(RetrievalLocationsError("malformed HTTP gzip content: $(sprint(showerror, error))"))
    finally
        if transcoded !== nothing
            try
                close(transcoded)
            catch
            end
        end
    end
    return bytes2hex(SHA.digest!(context)), count
end

function _decoded_http_body(response, url)
    body = response.body
    body isa Vector{UInt8} ||
        throw(RetrievalLocationsError("HTTP response from $url has no byte body"))
    _validate_transfer_headers(response, length(body), url)
    coding = _content_coding(response, url)
    coding === nothing && return body
    output = IOBuffer()
    open_input = IOBuffer(body)
    _copy_and_hash(open_input, output; gzip=true, strict_stream=true)
    return take!(output)
end

function _download_to_temp(url, directory)
    mkpath(directory)
    encoded_path, encoded_io = mktemp(directory; cleanup=false)
    decoded_path = nothing
    decoded_io = nothing
    try
        response = try
            HTTP.request(
                "GET",
                url,
                ["Accept-Encoding" => "identity"];
                response_stream=encoded_io,
                decompress=false,
                status_exception=false,
                redirect=true,
                redirect_limit=10,
            )
        catch error
            throw(RetrievalLocationsError("cannot retrieve $url: $(sprint(showerror, error))"))
        finally
            flush(encoded_io)
            close(encoded_io)
        end
        200 <= response.status < 300 ||
            throw(RetrievalLocationsError("HTTP $(response.status) from $url"))
        _validate_redirects(response)
        final_url = string(response.request_url)
        _is_http_url(final_url) ||
            throw(RetrievalLocationsError("request redirected to a non-HTTP(S) URL"))
        encoded_size = filesize(encoded_path)
        _validate_transfer_headers(response, encoded_size, url)
        coding = _content_coding(response, url)
        decoded_path, decoded_io = mktemp(directory; cleanup=false)
        digest, size = open(encoded_path, "r") do source
            result = _copy_and_hash(
                source,
                decoded_io;
                gzip=coding !== nothing,
                strict_stream=coding !== nothing,
            )
            flush(decoded_io)
            synced = Sys.iswindows() ?
                     ccall(:_commit, Cint, (Cint,), Base.fd(decoded_io)) :
                     ccall(:fsync, Cint, (Cint,), Base.fd(decoded_io))
            synced == 0 ||
                throw(CacheError("cannot flush downloaded object"))
            return result
        end
        close(decoded_io)
        rm(encoded_path; force=true)
        return decoded_path, digest, size
    catch
        isopen(encoded_io) && close(encoded_io)
        decoded_io !== nothing && isopen(decoded_io) && close(decoded_io)
        isfile(encoded_path) && rm(encoded_path; force=true)
        decoded_path !== nothing && isfile(decoded_path) && rm(decoded_path; force=true)
        rethrow()
    end
end

function _retrieve_cached_object(
    cache_dir,
    namespace,
    digest,
    size,
    urls,
    offline,
    integrity_type,
    offline_type,
    retrieval_type,
)
    path = _object_path(cache_dir, namespace, digest)
    lease = _acquire_lease(_lease_path(cache_dir, namespace, digest); exclusive=false)
    try
        if isfile(path)
            if _object_matches(path, digest, size)
                return CachedObject(path, lease)
            elseif offline
                throw(integrity_type("cached object does not match its registered identity"))
            end
        elseif offline
            throw(offline_type("verified cached object is unavailable while offline"))
        end

        failures = String[]
        saw_integrity = false
        for url in urls
            _is_http_url(url) || throw(UnsupportedRegistryError("artifact URL is invalid"))
            temporary = nothing
            try
                temporary, actual_digest, actual_size = _download_to_temp(url, dirname(path))
                if actual_digest != digest || (size !== nothing && actual_size != size)
                    saw_integrity = true
                    push!(failures, "$url: size or SHA-256 mismatch")
                    rm(temporary; force=true)
                    temporary = nothing
                    continue
                end
                _with_lease(
                    _lease_path(cache_dir, namespace, digest; publication=true);
                    exclusive=true,
                ) do _
                    if isfile(path)
                        if _object_matches(path, digest, size)
                            rm(temporary; force=true)
                            temporary = nothing
                            return
                        end
                        rm(path; force=true)
                    end
                    mv(temporary, path)
                    temporary = nothing
                end
                return CachedObject(path, lease)
            catch error
                error isa CacheError && rethrow()
                error isa UnsupportedRegistryError && rethrow()
                push!(failures, "$url: $(sprint(showerror, error))")
            finally
                temporary !== nothing && isfile(temporary) && rm(temporary; force=true)
            end
        end
        message = "all retrieval locations failed: " * join(failures, "; ")
        throw(saw_integrity ? integrity_type(message) : retrieval_type(message))
    catch
        _release_lease(lease)
        rethrow()
    end
end

_release_cached(object::CachedObject) = _release_lease(object.lease)

function _cached_index_records(cache_dir)
    records = Tuple{Dict{String,Any},Union{Nothing,String}}[]
    bundled = joinpath(@__DIR__, "data", "index.json")
    try
        push!(records, (JSON3.read(read(bundled), Dict{String,Any}), "proof-0001"))
    catch
    end
    directory = joinpath(cache_dir, "registries", "sha256")
    isdir(directory) || return records
    for path in readdir(directory; join=true)
        isfile(path) || continue
        digest = basename(path)
        occursin(_SHA256_PATTERN, digest) || continue
        actual, _ = _file_digest_and_size(path)
        actual == digest || continue
        try
            index = JSON3.read(read(path), Dict{String,Any})
            release = get(index, "release", nothing)
            push!(records, (index, release isa String ? release : nothing))
        catch
        end
    end
    return records
end

function _cache_associations(cache_dir)
    datasets = Dict{String,Set{String}}()
    for (index, _) in _cached_index_records(cache_dir)
        for dataset in get(index, "datasets", Any[])
            dataset isa AbstractDict || continue
            id = "$(get(dataset, "source", "")):$(get(dataset, "name", ""))@$(get(dataset, "version", ""))"
            for artifact in get(dataset, "artifacts", Any[])
                digest = get(artifact, "sha256", nothing)
                digest isa String || continue
                push!(get!(datasets, digest, Set{String}()), id)
            end
        end
    end
    return datasets
end

"""Verify and inventory cached registry indexes and artifacts."""
function cache_info(; cache_dir=nothing)
    cache_dir = datamonger_cache_dir(cache_dir)
    ispath(cache_dir) && !isdir(cache_dir) &&
        throw(CacheError("cache root is not a directory"))
    associations = _cache_associations(cache_dir)
    entries = CacheEntry[]
    total_size = Int64(0)
    for (namespace, kind) in (("objects", :artifact), ("registries", :registry))
        directory = joinpath(cache_dir, namespace, "sha256")
        ispath(directory) && !isdir(directory) &&
            throw(CacheError("cache namespace path is not a directory"))
        isdir(directory) || continue
        for path in sort(readdir(directory; join=true))
            isfile(path) || continue
            digest = basename(path)
            size = Int64(filesize(path))
            total_size += size
            valid = occursin(_SHA256_PATTERN, digest) && first(_file_digest_and_size(path)) == digest
            release = nothing
            if kind == :registry && valid
                try
                    parsed = JSON3.read(read(path), Dict{String,Any})
                    value = get(parsed, "release", nothing)
                    release = value isa String ? value : nothing
                catch
                end
            end
            push!(entries, CacheEntry(
                kind,
                digest,
                size,
                Dates.unix2datetime(stat(path).mtime),
                path,
                valid,
                sort!(collect(get(associations, digest, Set{String}()))),
                release,
            ))
        end
    end
    return CacheInfo(cache_dir, total_size, entries)
end

function _period_seconds(period::Dates.Period)
    return Dates.value(Dates.Millisecond(period)) / 1000
end

"""Remove selected inactive cache entries, skipping active readers and publishers."""
function cache_clean(; dataset=nothing, older_than=nothing, cache_dir=nothing)
    cache_dir = datamonger_cache_dir(cache_dir)
    dataset === nothing || dataset isa String && occursin(_DATASET_ID_PATTERN, dataset) ||
        throw(ArgumentError("dataset must be a canonical source:name@version identifier"))
    info = cache_info(; cache_dir)
    threshold = if older_than === nothing
        nothing
    elseif older_than isa Real
        isfinite(older_than) && older_than >= 0 ||
            throw(ArgumentError("older_than must be nonnegative"))
        time() - older_than
    elseif older_than isa Dates.Period
        seconds = _period_seconds(older_than)
        seconds >= 0 || throw(ArgumentError("older_than must be nonnegative"))
        time() - seconds
    else
        throw(ArgumentError("older_than must be seconds or a Dates.Period"))
    end
    removed = CacheEntry[]
    skipped = CacheEntry[]
    for entry in info.entries
        dataset !== nothing && !(dataset in entry.datasets) && continue
        threshold !== nothing && datetime2unix(entry.modified_at) > threshold && continue
        namespace = entry.kind == :artifact ? "objects" : "registries"
        if !occursin(_SHA256_PATTERN, entry.sha256)
            rm(entry.path; force=true)
            push!(removed, entry)
            continue
        end
        lease = _acquire_lease(
            _lease_path(cache_dir, namespace, entry.sha256);
            exclusive=true,
            blocking=false,
        )
        if lease === nothing
            push!(skipped, entry)
            continue
        end
        try
            isfile(entry.path) || continue
            current_stat = stat(entry.path)
            threshold !== nothing && current_stat.mtime > threshold && continue
            current = CacheEntry(
                entry.kind,
                entry.sha256,
                Int64(current_stat.size),
                Dates.unix2datetime(current_stat.mtime),
                entry.path,
                entry.valid,
                entry.datasets,
                entry.registry_release,
            )
            rm(entry.path)
            push!(removed, current)
        catch error
            throw(CacheError("cannot remove cache entry: $(sprint(showerror, error))"))
        finally
            _release_lease(lease)
        end
    end
    return CacheCleanResult(
        info.location,
        removed,
        skipped,
        sum(entry.size for entry in removed; init=Int64(0)),
    )
end
