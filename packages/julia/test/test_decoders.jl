@testset "shared decoder conformance" begin
    document = read_json("conformance", "cases.json")
    @test document["schema_version"] == 1
    @test document["canonical_form"] == 1
    for case in document["cases"]
        recipe = case["recipe"]
        decoded = if case["decoder"] == "delimited-text"
            Datamonger.decode_delimited(
                joinpath(FIXTURES, "conformance", case["input"]),
                recipe,
            )
        elseif case["decoder"] == "libsvm"
            Datamonger.decode_libsvm(
                joinpath(FIXTURES, "conformance", case["input"]),
                recipe,
            )
        else
            Datamonger.decode_libsvm_split(
                joinpath(FIXTURES, "conformance", case["input"]["train"]),
                joinpath(FIXTURES, "conformance", case["input"]["test"]),
                recipe,
            )
        end
        @test Datamonger.canonical_sha256(decoded.components) ==
              case["expected_sha256"]
    end
end

@testset "declared artifact compression" begin
    cases = read_json("conformance", "cases.json")["cases"]
    for compression in ("gzip", "bzip2")
        for case_index in (1, 3)
            case = cases[case_index]
            source = read(joinpath(FIXTURES, "conformance", case["input"]))
            encoded = compressed_bytes(source, compression)
            path = write_bytes(encoded)
            decoded = case["decoder"] == "delimited-text" ?
                      Datamonger.decode_delimited(path, case["recipe"]; compression) :
                      Datamonger.decode_libsvm(path, case["recipe"]; compression)
            @test Datamonger.canonical_sha256(decoded.components) ==
                  case["expected_sha256"]
            rm(path)

            truncated = write_bytes(encoded[1:end-1])
            if case["decoder"] == "delimited-text"
                @test_throws DecodeError Datamonger.decode_delimited(
                    truncated,
                    case["recipe"];
                    compression,
                )
            else
                @test_throws DecodeError Datamonger.decode_libsvm(
                    truncated,
                    case["recipe"];
                    compression,
                )
            end
            rm(truncated)
        end
    end
end

@testset "malformed decoder inputs" begin
    for case in read_json("conformance", "malformed.json")["cases"]
        recipe = case["recipe"]
        run = if case["decoder"] == "delimited-text"
            () -> Datamonger.decode_delimited(
                joinpath(FIXTURES, "conformance", case["input"]),
                recipe,
            )
        elseif case["decoder"] == "libsvm"
            () -> Datamonger.decode_libsvm(
                joinpath(FIXTURES, "conformance", case["input"]),
                recipe,
            )
        else
            () -> Datamonger.decode_libsvm_split(
                joinpath(FIXTURES, "conformance", case["input"]["train"]),
                joinpath(FIXTURES, "conformance", case["input"]["test"]),
                recipe,
            )
        end
        @test_throws DecodeError run()
    end

    cases = read_json("conformance", "cases.json")["cases"]
    csv_recipe = deepcopy(cases[1]["recipe"])
    csv_recipe["columns"] = Any[Dict("name" => "x", "type" => "string")]
    svm_recipe = cases[3]["recipe"]
    for case in read_json("conformance", "fuzz-regressions.json")["cases"]
        path = write_bytes(hex2bytes(case["input_hex"]))
        run = case["decoder"] == "delimited-text" ?
              () -> Datamonger.decode_delimited(path, csv_recipe) :
              () -> Datamonger.decode_libsvm(path, svm_recipe)
        @test_throws DecodeError run()
        rm(path)
    end
end

@testset "strict decoder details" begin
    cases = read_json("conformance", "cases.json")["cases"]
    recipe = deepcopy(cases[1]["recipe"])
    recipe["columns"] = Any[Dict("name" => "x", "type" => "float64")]
    for value in [" 1", "+1", "NaN", "1e999"]
        path = write_bytes(Vector{UInt8}(codeunits("x\n$value\n")))
        @test_throws DecodeError Datamonger.decode_delimited(path, recipe)
        rm(path)
    end

    recipe["columns"] = Any[Dict("name" => "x", "type" => "int64")]
    path = write_bytes(Vector{UInt8}(codeunits(
        "x\r\n9223372036854775807\r\n-9223372036854775808",
    )))
    decoded = Datamonger.decode_delimited(path, recipe)
    @test decoded.data.x == Int64[typemax(Int64), typemin(Int64)]
    rm(path)

    svm_recipe = cases[3]["recipe"]
    for body in [
        "\n",
        "+1 1:0\n",
        "+1 1:1 1:2\n",
        "+1 2:1 1:2\n",
        "+1 5:1\n",
        "+1 01:1\n",
        "+1 qid:1 1:1\n",
        "+1 1:1 # comment\n",
        "+01 1:1\n",
        " +1 1:1\n",
    ]
        path = write_bytes(Vector{UInt8}(codeunits(body)))
        @test_throws DecodeError Datamonger.decode_libsvm(path, svm_recipe)
        rm(path)
    end

    wide_recipe = deepcopy(svm_recipe)
    wide_recipe["feature_count"] = 2_147_483_648
    empty = write_bytes(UInt8[])
    wide = Datamonger.decode_libsvm(empty, wide_recipe)
    @test wide.data.features isa CSRMatrix
    @test size(wide.data.features) == (0, 2_147_483_648)
    @test nnz(wide.data.features) == 0
    rm(empty)

    invalid_recipe = deepcopy(svm_recipe)
    invalid_recipe["index_base"] = true
    @test_throws UnsupportedDecoderError Datamonger.decode_libsvm(
        joinpath(FIXTURES, "conformance", cases[3]["input"]),
        invalid_recipe,
    )
end
