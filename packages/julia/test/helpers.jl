const FIXTURES = joinpath(@__DIR__, "fixtures")

read_json(path...) = JSON3.read(
    read(joinpath(FIXTURES, path...)),
    Dict{String,Any},
)

function seed_conformance_cache(cache_dir)
    selector = read_json("registry", "selector.json")
    index = read_json("registry", "index.json")
    registry_dir = joinpath(cache_dir, "registries", "sha256")
    object_dir = joinpath(cache_dir, "objects", "sha256")
    mkpath(registry_dir)
    mkpath(object_dir)
    cp(
        joinpath(FIXTURES, "registry", "index.json"),
        joinpath(registry_dir, selector["index_sha256"]),
    )
    for path in readdir(joinpath(FIXTURES, "conformance", "artifacts"); join=true)
        digest = bytes2hex(sha256(read(path)))
        cp(path, joinpath(object_dir, digest))
    end
    return (
        selector=Registry(
            selector["release"],
            selector["index_sha256"],
            selector["index_url"],
        ),
        index=index,
    )
end

function write_bytes(bytes)
    path, io = mktemp()
    write(io, bytes)
    close(io)
    return path
end

function compressed_bytes(bytes, compression)
    return compression == "gzip" ?
           transcode(GzipCompressor, bytes) : transcode(Bzip2Compressor, bytes)
end

function reseal_index(index, cache_dir)
    bytes = Vector{UInt8}(codeunits(JSON3.write(index)))
    digest = bytes2hex(sha256(bytes))
    directory = joinpath(cache_dir, "registries", "sha256")
    mkpath(directory)
    write(joinpath(directory, digest), bytes)
    return Registry(index["release"], digest, "https://example.com/index.json")
end
