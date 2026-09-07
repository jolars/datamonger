include("helpers.jl")

@testset "canonical form" begin
    document = read_json("conformance", "canonical", "cases.json")
    @test document["schema_version"] == 1
    @test document["canonical_form"] == 1
    for case in document["cases"]
        component = Datamonger.component_from_descriptor(case["component"])
        @test bytes2hex(Datamonger.canonical_bytes([component])) ==
              case["expected_hex"]
    end
end

@testset "canonical sparse validation" begin
    nan_component = Datamonger.LogicalSparseMatrix(
        "x",
        1,
        1,
        [0, 1],
        [0],
        [NaN],
    )
    @test Datamonger.canonical_bytes([nan_component])[end-7:end] ==
          hex2bytes("000000000000f87f")

    invalid = [
        Datamonger.LogicalSparseMatrix("x", 1, 2, [0, 2], [0, 0], [1.0, 2.0]),
        Datamonger.LogicalSparseMatrix("x", 1, 2, [0, 1], [2], [1.0]),
        Datamonger.LogicalSparseMatrix("x", 1, 2, [0, 1], [0], [0.0]),
        Datamonger.LogicalSparseMatrix("x", 1, 2, [1, 1], Int[], Float64[]),
        Datamonger.LogicalSparseMatrix("x", 2, 2, [0, 1, 0], [0], [1.0]),
        Datamonger.LogicalSparseMatrix("x", 1, 1, [0, 1], [0], [Inf]),
    ]
    for component in invalid
        @test_throws DecodedIntegrityError Datamonger.canonical_bytes([component])
    end
end
