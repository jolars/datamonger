@testset "registry selection" begin
    digest = repeat("a", 64)
    selected = Registry("candidate-0002", digest, "https://example.com/index.json")
    @test selected.schema_version == 1
    @test_throws RegistryIntegrityError Registry(
        "candidate",
        "ABC",
        "https://example.com/index.json",
    )
    @test_throws RegistryError Registry(
        "candidate",
        digest,
        "file:///tmp/index",
    )
    @test_throws UnsupportedRegistryError Registry(
        "candidate",
        digest,
        "https://example.com/index.json",
        true,
    )

    previous = active_registry(; project_dir=mktempdir())
    set_registry!(selected)
    @test active_registry(; project_dir=mktempdir()) == selected
    set_registry!(nothing)
    @test active_registry(; project_dir=mktempdir()) == previous

    root = mktempdir()
    child = joinpath(root, "analysis", "notebooks")
    selector_dir = joinpath(root, "analysis", ".datamonger")
    mkpath(child)
    mkpath(selector_dir)
    write(
        joinpath(selector_dir, "selector.json"),
        JSON3.write(Dict(
            "schema_version" => 1,
            "release" => "project-1",
            "index_sha256" => digest,
            "index_url" => "https://example.com/index.json",
        )),
    )
    @test active_registry(; project_dir=child).release == "project-1"
end

@testset "bundled registry" begin
    listed = list_data(; cache_dir=mktempdir(), offline=true)
    @test Set(info.dataset_id for info in listed) ==
          Set(["libsvm:heart_scale@1", "uci:iris@1"])
end

@testset "registry identity and offline failures" begin
    cache_dir = mktempdir()
    uncached = Registry(
        "missing-1",
        repeat("a", 64),
        "https://example.com/index.json",
    )
    @test_throws RegistryOfflineError list_data(; registry=uncached, cache_dir, offline=true)

    bytes = read(joinpath(FIXTURES, "registry", "index.json"))
    digest = bytes2hex(sha256(bytes))
    directory = joinpath(cache_dir, "registries", "sha256")
    mkpath(directory)
    write(joinpath(directory, digest), bytes)
    wrong_release = Registry("other-1", digest, "https://example.com/index.json")
    @test_throws RegistryReleaseError list_data(
        ; registry=wrong_release, cache_dir, offline=true,
    )

    corrupt_digest = repeat("b", 64)
    write(joinpath(directory, corrupt_digest), "wrong")
    corrupt = Registry(
        "test-0002",
        corrupt_digest,
        "https://example.com/index.json",
    )
    @test_throws RegistryIntegrityError list_data(
        ; registry=corrupt, cache_dir, offline=true,
    )
end
