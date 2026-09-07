@testset "cache inventory and cleaning" begin
    cache_dir = mktempdir()
    directory = joinpath(cache_dir, "objects", "sha256")
    mkpath(directory)
    bytes = Vector{UInt8}(codeunits("artifact"))
    digest = bytes2hex(sha256(bytes))
    write(joinpath(directory, digest), bytes)
    corrupt_digest = bytes2hex(sha256(Vector{UInt8}(codeunits("other"))))
    write(joinpath(directory, corrupt_digest), "corrupt")

    info = cache_info(; cache_dir)
    @test info.total_size == 15
    @test Set(entry.sha256 for entry in info.entries) == Set([digest, corrupt_digest])
    @test only(entry.valid for entry in info.entries if entry.sha256 == digest)
    @test !only(entry.valid for entry in info.entries if entry.sha256 == corrupt_digest)

    result = cache_clean(; cache_dir, older_than=0)
    @test length(result.removed) == 2
    @test result.bytes_removed == 15
    @test !isfile(joinpath(directory, digest))
end

@testset "persistent cache requires consent" begin
    previous = get(ENV, "DATAMONGER_CACHE_CONSENT", nothing)
    try
        Datamonger._CACHE_CONSENT[] = nothing
        delete!(ENV, "DATAMONGER_CACHE_CONSENT")
        @test startswith(datamonger_cache_dir(), tempdir())

        Datamonger._CACHE_CONSENT[] = nothing
        ENV["DATAMONGER_CACHE_CONSENT"] = "true"
        @test datamonger_cache_dir() == default_cache_dir()

        explicit = mktempdir()
        @test datamonger_cache_dir(explicit) == abspath(explicit)
    finally
        Datamonger._CACHE_CONSENT[] = nothing
        if previous === nothing
            delete!(ENV, "DATAMONGER_CACHE_CONSENT")
        else
            ENV["DATAMONGER_CACHE_CONSENT"] = previous
        end
    end
end

@testset "invalid cache roots use the cache category" begin
    path, io = mktemp()
    close(io)
    @test_throws CacheError cache_info(; cache_dir=path)
    rm(path)
end

@testset "active cache leases exclude cleaners" begin
    cache_dir = mktempdir()
    bytes = Vector{UInt8}(codeunits("active"))
    digest = bytes2hex(sha256(bytes))
    directory = joinpath(cache_dir, "objects", "sha256")
    mkpath(directory)
    path = joinpath(directory, digest)
    write(path, bytes)
    lease = Datamonger._acquire_lease(
        Datamonger._lease_path(cache_dir, "objects", digest);
        exclusive=false,
    )
    try
        result = cache_clean(; cache_dir)
        @test isempty(result.removed)
        @test length(result.skipped) == 1
        @test isfile(path)
    finally
        Datamonger._release_lease(lease)
    end
end

@testset "verified retrieval and HTTP boundaries" begin
    expected = Vector{UInt8}(codeunits("expected"))
    digest = bytes2hex(sha256(expected))
    encoded = compressed_bytes(expected, "gzip")
    requested = String[]
    accept_encoding = String[]
    server = HTTP.serve!("127.0.0.1", 0; listenany=true) do request
        target = String(request.target)
        push!(requested, target)
        push!(accept_encoding, HTTP.header(request, "Accept-Encoding", ""))
        if target == "/bad"
            return HTTP.Response(200; body="bad")
        elseif target == "/good"
            return HTTP.Response(200; body=expected)
        elseif target == "/gzip"
            return HTTP.Response(
                200;
                headers=["Content-Encoding" => "gzip"],
                body=encoded,
            )
        elseif target == "/concatenated"
            return HTTP.Response(
                200;
                headers=["Content-Encoding" => "gzip"],
                body=[encoded; encoded],
            )
        elseif target == "/relative-redirect"
            return HTTP.Response(302; headers=["Location" => "/good"])
        end
        return HTTP.Response(404; body="missing")
    end
    base = "http://127.0.0.1:$(HTTP.port(server))"
    try
        cache_dir = mktempdir()
        object = Datamonger._retrieve_cached_object(
            cache_dir,
            "objects",
            digest,
            length(expected),
            [base * "/bad", base * "/good"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
        try
            @test read(object.path) == expected
            @test requested == ["/bad", "/good"]
            @test accept_encoding == ["identity", "identity"]
        finally
            Datamonger._release_cached(object)
        end

        gzip_object = Datamonger._retrieve_cached_object(
            mktempdir(),
            "objects",
            digest,
            length(expected),
            [base * "/gzip"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
        try
            @test read(gzip_object.path) == expected
        finally
            Datamonger._release_cached(gzip_object)
        end

        @test_throws RetrievalLocationsError Datamonger._retrieve_cached_object(
            mktempdir(),
            "objects",
            digest,
            length(expected),
            [base * "/concatenated"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
        @test_throws RetrievalLocationsError Datamonger._retrieve_cached_object(
            mktempdir(),
            "objects",
            digest,
            length(expected),
            [base * "/relative-redirect"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
        @test_throws ArtifactIntegrityError Datamonger._retrieve_cached_object(
            mktempdir(),
            "objects",
            digest,
            length(expected),
            [base * "/bad"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
        @test_throws RetrievalLocationsError Datamonger._retrieve_cached_object(
            mktempdir(),
            "objects",
            digest,
            length(expected),
            [base * "/missing"],
            false,
            ArtifactIntegrityError,
            OfflineError,
            RetrievalLocationsError,
        )
    finally
        HTTP.forceclose(server)
    end
end

@testset "offline cache failures remain distinct" begin
    cache_dir = mktempdir()
    digest = repeat("a", 64)
    @test_throws OfflineError Datamonger._retrieve_cached_object(
        cache_dir,
        "objects",
        digest,
        1,
        ["https://example.com/missing"],
        true,
        ArtifactIntegrityError,
        OfflineError,
        RetrievalLocationsError,
    )
    path = joinpath(cache_dir, "objects", "sha256", digest)
    mkpath(dirname(path))
    write(path, "wrong")
    @test_throws ArtifactIntegrityError Datamonger._retrieve_cached_object(
        cache_dir,
        "objects",
        digest,
        1,
        ["https://example.com/missing"],
        true,
        ArtifactIntegrityError,
        OfflineError,
        RetrievalLocationsError,
    )
end
