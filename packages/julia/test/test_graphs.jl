@testset "graph and HIF retrieval" begin
    cases = read_json("conformance", "graphs.json")["cases"]
    for case in cases
        mktempdir() do cache_dir
            registry = seed_split_case(case, cache_dir)
            reference = "conformance:$(case["id"])@1"
            Datamonger._native_symbol(:dm_abi_version)
            symbol = case["id"] == "graph" ? :dm_assemble_graph : :dm_decode_hif
            if Datamonger.Libdl.dlsym_e(Datamonger._NATIVE_LIBRARY[], symbol) == C_NULL
                @test_throws UnsupportedDecoderError fetch_data(reference; registry, cache_dir, offline=true)
                return
            end
            result = fetch_data(reference; registry, cache_dir, offline=true, return_info=true)
            @test result.info.canonical_digest == bytes2hex(sha256(hex2bytes(case["expected_hex"])))
            @test Set(keys(result.info.artifact_digests)) == Set(keys(case["artifact_paths"]))
            if case["id"] == "graph"
                @test result.data isa GraphDataset
                @test result.data.nodes.id == [9007199254740993, 7]
                @test result.data.edges.source == fill(9007199254740993, 2)
            else
                @test result.data isa HypergraphDataset
                @test result.data.nodes.id == ["isolate", "inferred"]
                @test ismissing(result.data.nodes.label[2])
                @test result.data.hyperedges.id == [9007199254740993]
            end
        end
    end
end
