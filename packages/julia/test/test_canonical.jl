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

@testset "canonical masked numeric storage" begin
    for (logical_type, value, zero) in (("float64", 1.5, 0.0),
                                       ("int64", Int64(42), Int64(0)),
                                       ("bool", true, false))
        for make_component in (
            (values, valid) -> Datamonger.LogicalVector("x", logical_type, values, valid),
            (values, valid) -> Datamonger.LogicalDenseMatrix(
                "x", logical_type, 1, length(values), values, valid,
            ),
        )
            for (values, normalized, valid) in (
                ([missing], [zero], [false]),
                ([value, missing, zero, missing], [value, zero, zero, zero],
                 [true, false, true, false]),
            )
                original_values = copy(values)
                component = make_component(values, valid)
                expected = Datamonger.canonical_bytes([make_component(normalized, valid)])
                @test Datamonger.canonical_bytes([component]) == expected
                @test Datamonger.canonical_sha256([component]) == bytes2hex(sha256(expected))
                @test isequal(component.values, original_values)
            end
        end
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
