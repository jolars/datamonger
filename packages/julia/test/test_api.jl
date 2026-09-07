@testset "public API conformance" begin
    cache_dir = mktempdir()
    seeded = seed_conformance_cache(cache_dir)

    info = data_info(
        "mixed_csv";
        source="conformance",
        registry=seeded.selector,
        cache_dir,
        offline=true,
    )
    @test info.dataset_id == "conformance:mixed_csv@1"
    @test !isempty(info.provenance["provider"])
    @test length(list_data(; registry=seeded.selector, cache_dir, offline=true)) == 5

    table = fetch_data(
        "mixed_csv";
        source="conformance",
        registry=seeded.selector,
        cache_dir,
        offline=true,
    )
    @test table isa DataFrame
    @test size(table) == (5, 4)
    @test table[2, :label] == "quoted, value"
    @test table[3, :label] == "says \"hello\""
    @test ismissing(table[3, :measurement])
    @test eltype(table.measurement) == Union{Missing,Float64}
    @test eltype(table.count) == Union{Missing,Int64}

    cases = read_json("conformance", "cases.json")["cases"]
    expected = Dict(case["dataset"] => case["expected_sha256"] for case in cases)
    for dataset in seeded.index["datasets"]
        result = fetch_data(
            dataset["name"];
            source=dataset["source"],
            version=dataset["version"],
            registry=seeded.selector,
            cache_dir,
            offline=true,
            return_info=true,
        )
        dataset_id = "$(dataset["source"]):$(dataset["name"])@$(dataset["version"])"
        @test result.info.verification == :decoded
        @test result.info.canonical_digest == expected[dataset_id]
    end

    result = fetch_data(
        "mixed_csv";
        source="conformance",
        registry=seeded.selector,
        cache_dir,
        offline=true,
        verify_decoded=false,
        return_info=true,
    )
    @test result.info.verification == :artifact
    @test isnothing(result.info.canonical_form)
    @test_throws UnknownDatasetError data_info(
        "missing";
        source="conformance",
        registry=seeded.selector,
        cache_dir,
        offline=true,
    )

    @test_throws ArtifactSelectionError fetch_artifact(
        "small_libsvm_split";
        source="conformance",
        registry=seeded.selector,
        cache_dir,
        offline=true,
    )
end

@testset "public semantic failures and errata" begin
    cache_dir = mktempdir()
    seeded = seed_conformance_cache(cache_dir)

    index = deepcopy(seeded.index)
    index["schema_version"] = 2
    unsupported_registry = reseal_index(index, cache_dir)
    @test_throws UnsupportedRegistryError list_data(
        ; registry=unsupported_registry, cache_dir, offline=true,
    )

    index = deepcopy(seeded.index)
    index["datasets"][1]["representation"]["decoder_version"] = 2
    unsupported_decoder = reseal_index(index, cache_dir)
    @test_throws UnsupportedDecoderError fetch_data(
        "mixed_csv";
        source="conformance",
        registry=unsupported_decoder,
        cache_dir,
        offline=true,
    )

    index = deepcopy(seeded.index)
    artifact = index["datasets"][1]["artifacts"][1]
    artifact["distribution"] = "metadata-only"
    delete!(artifact, "downloads")
    metadata_only = reseal_index(index, cache_dir)
    @test_throws ArtifactUnavailableError fetch_artifact(
        "mixed_csv";
        source="conformance",
        registry=metadata_only,
        cache_dir,
        offline=true,
    )

    index = deepcopy(seeded.index)
    index["datasets"][1]["representation"]["expect"]["verification"][1]["digest"] =
        repeat("0", 64)
    mismatch = reseal_index(index, cache_dir)
    @test_throws DecodedIntegrityError fetch_data(
        "mixed_csv";
        source="conformance",
        registry=mismatch,
        cache_dir,
        offline=true,
    )

    index = deepcopy(seeded.index)
    dataset = index["datasets"][1]
    replacement = deepcopy(dataset["representation"]["expect"]["verification"][1])
    original = Dict(
        "canonical_form" => 1,
        "algorithm" => "sha256",
        "digest" => repeat("0", 64),
    )
    dataset["representation"]["expect"]["verification"] = Any[original, replacement]
    index["errata"] = Any[Dict(
        "schema_version" => 1,
        "id" => "mixed-csv-verification",
        "release" => index["release"],
        "dataset" => Dict(
            "name" => dataset["name"],
            "version" => dataset["version"],
            "source" => dataset["source"],
        ),
        "target" => Dict(
            "kind" => "verification",
            "canonical_form" => 1,
            "algorithm" => "sha256",
        ),
        "original" => Dict(
            "algorithm" => original["algorithm"],
            "digest" => original["digest"],
            "canonical_form" => original["canonical_form"],
        ),
        "replacement" => replacement,
        "reason" => "The earlier digest was incorrect.",
        "approval" => Dict(
            "maintainer" => "fixture",
            "approved_at" => "2026-09-07",
        ),
    )]
    corrected = reseal_index(index, cache_dir)
    result = fetch_data(
        dataset["name"];
        source=dataset["source"],
        version=dataset["version"],
        registry=corrected,
        cache_dir,
        offline=true,
        return_info=true,
    )
    @test result.info.canonical_digest == replacement["digest"]
end

@testset "semantic taxonomy is complete" begin
    expected = Set(case["expected"] for case in read_json("conformance", "errors.json")["cases"])
    @test Set(keys(Datamonger.SEMANTIC_ERROR_CATEGORIES)) == expected
end
