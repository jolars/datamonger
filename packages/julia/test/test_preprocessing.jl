@testset "preprocessing metadata contract" begin
    cache_dir = mktempdir()
    seeded = seed_conformance_cache(cache_dir)
    baseline = fetch_data("conformance:mixed_csv@1";
        registry=seeded.selector, cache_dir, offline=true, return_info=true)
    for case in read_json("conformance", "preprocessing.json")["cases"]
        @testset "$(case["id"])" begin
            index = deepcopy(seeded.index)
            index["schema_version"] = 3
            dataset = index["datasets"][1]
            dataset["schema_version"] = case["manifest_schema_version"]
            if haskey(case, "preprocessing")
                dataset["preprocessing"] = deepcopy(case["preprocessing"])
            end
            options = (; registry=reseal_index(index, cache_dir), cache_dir, offline=true)
            if case["expected"] == "invalid"
                @test_throws UnsupportedRegistryError data_info("conformance:mixed_csv@1"; options...)
                @test_throws UnsupportedRegistryError fetch_data("conformance:mixed_csv@1"; options...)
            else
                info = data_info("conformance:mixed_csv@1"; options...)
                result = fetch_data("conformance:mixed_csv@1"; options..., return_info=true)
                @test info.preprocessing == get(case, "preprocessing", nothing)
                @test result.info.preprocessing == info.preprocessing
                @test isequal(result.data, baseline.data)
                @test result.info.canonical_digest == baseline.info.canonical_digest
                @test first(list_data(; options...)).preprocessing == info.preprocessing
            end
        end
    end
end
