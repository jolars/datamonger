function seed_split_case(case, cache_dir, compression="none")
    dataset = deepcopy(case["manifest"])
    directory = joinpath(cache_dir, "objects", "sha256")
    mkpath(directory)
    for artifact in dataset["artifacts"]
        bytes = read(joinpath(FIXTURES, "conformance", case["artifact_paths"][artifact["name"]]))
        if compression != "none"
            bytes = compressed_bytes(bytes, compression)
        end
        artifact["compression"] = compression
        artifact["size"] = length(bytes)
        artifact["sha256"] = bytes2hex(sha256(bytes))
        write(joinpath(directory, artifact["sha256"]), bytes)
    end
    index = Dict("schema_version" => 4, "release" => "named-splits-test",
                 "datasets" => [dataset], "defaults" => Any[])
    return reseal_index(index, cache_dir)
end

@testset "provider-named splits" begin
    document = read_json("conformance", "named-splits.json")
    for case in document["cases"], compression in ("none", "gzip", "bzip2")
        @testset "$(case["id"]) $compression" begin
            cache_dir = mktempdir()
            registry = seed_split_case(case, cache_dir, compression)
            result = fetch_data("conformance:$(case["id"])@1";
                registry, cache_dir, offline=true, return_info=true)
            @test result.data isa DatasetSplits
            @test collect(keys(result.data)) == [s["name"] for s in case["expected_splits"]]
            @test [first(pair) for pair in result.data] == collect(keys(result.data))
            first_name = first(keys(result.data))
            @test get(result.data, first_name, nothing) === result.data[first_name]
            @test get(result.data, "missing split", nothing) === nothing
            @test get(() -> nothing, result.data, "missing split") === nothing
            @test result.info.verification == :decoded
            @test Set(keys(result.info.artifact_digests)) == Set(keys(case["artifact_paths"]))
            unchecked = fetch_data("conformance:$(case["id"])@1";
                registry, cache_dir, offline=true, verify_decoded=false, return_info=true)
            @test collect(keys(unchecked.data)) == collect(keys(result.data))
            @test unchecked.info.verification == :artifact
            @test isnothing(unchecked.info.canonical_digest)
            @test result.info.canonical_digest == bytes2hex(sha256(hex2bytes(case["expected_hex"])))
            for expected in case["expected_splits"]
                split = result.data[expected["name"]]
                if expected["kind"] == "sparse"
                    @test split isa SparseDataset
                    @test Matrix(split.features) == reduce(vcat, permutedims.(expected["features"]))
                    @test split.response == expected["response"]
                else
                    @test split isa DataFrame
                    @test names(split) == expected["columns"]
                    for column in names(split)
                        @test split[!, column] == expected["values"][column]
                    end
                end
            end
            setup = Datamonger._validate_representation(case["manifest"])
            paths = [joinpath(FIXTURES, "conformance", case["artifact_paths"][a["name"]])
                     for a in case["manifest"]["artifacts"]]
            decoded = Datamonger._decode_setup(setup, paths)
            @test bytes2hex(Datamonger.canonical_bytes(decoded.components)) == case["expected_hex"]
        end
    end
    for invalid in document["invalid"]
        @testset "$(invalid["id"])" begin
            case = deepcopy(document["cases"][1])
            case["manifest"]["representation"] = invalid["representation"]
            cache_dir = mktempdir()
            registry = seed_split_case(case, cache_dir)
            @test_throws UnsupportedDecoderError fetch_data("conformance:three-provider-splits@1";
                registry, cache_dir, offline=true)
        end
    end
    for mutation in ("order", "membership")
        case = deepcopy(document["cases"][1])
        representation = case["manifest"]["representation"]
        if mutation == "order"
            reverse!(representation["options"]["splits"])
        else
            representation["inputs"]["validation"] = representation["inputs"]["train"]
        end
        cache_dir = mktempdir()
        registry = seed_split_case(case, cache_dir)
        @test_throws DecodedIntegrityError fetch_data("conformance:three-provider-splits@1";
            registry, cache_dir, offline=true)
    end
end
