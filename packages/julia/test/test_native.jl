include("reference/Reference.jl")

function compare_components(actual, expected)
    @test length(actual) == length(expected)
    for (a, e) in zip(actual, expected)
        @test typeof(a) == typeof(e)
        @test a.name == e.name
        # Broadcasting over an empty Any[] leaves the old internal string
        # buffer untyped; the public DataFrame column still has its declared type.
        if !(isempty(e.values) && eltype(e.values) == Any)
            @test eltype(a.values) == eltype(e.values)
        end
        if a isa Datamonger.LogicalSparseMatrix
            @test (a.rows, a.columns) == (e.rows, e.columns)
            @test a.row_offsets == e.row_offsets
            @test a.column_indices == e.column_indices
        else
            @test a.logical_type == e.logical_type
            @test a.valid == e.valid
        end
        if eltype(a.values) == Float64
            @test reinterpret(UInt64, a.values) == reinterpret(UInt64, e.values)
        else
            @test a.values == e.values
        end
    end
    golden = Reference.canonical_bytes(expected)
    @test Datamonger.canonical_bytes(actual) == golden
    @test Datamonger.canonical_bytes(expected) == golden
    @test Reference.canonical_bytes(actual) == golden
    @test Datamonger.canonical_sha256(actual) == bytes2hex(sha256(golden))
end

function compare_data(actual, expected)
    @test typeof(actual) == typeof(expected)
    if actual isa DataFrame
        @test isequal(actual, expected)
    elseif actual isa SparseDataset
        @test isequal(actual.response, expected.response)
        if actual.features isa CSRMatrix
            @test actual.features.row_offsets == expected.features.row_offsets
            @test actual.features.column_indices == expected.features.column_indices
            @test actual.features.values == expected.features.values
        else
            @test actual.features == expected.features
        end
    else
        compare_data(actual.train, expected.train)
        compare_data(actual.test, expected.test)
    end
end

function compare_decoded(actual, expected)
    compare_components(actual.components, expected.components)
    compare_data(actual.data, expected.data)
end

function decode_case(backend, case; compressions=("none", "none"))
    input = case["input"]
    inputs = input isa AbstractDict ? [input["train"], input["test"]] : [input]
    mktempdir() do directory
        paths = map(enumerate(inputs)) do (i, input)
            bytes = read(joinpath(FIXTURES, "conformance", input))
            compression = compressions[i]
            path = joinpath(directory, "artifact-$i")
            write(path, compression == "none" ? bytes : compressed_bytes(bytes, compression))
            path
        end
        if case["decoder"] == "delimited-text"
            backend.decode_delimited(paths[1], case["recipe"]; compression=compressions[1])
        elseif case["decoder"] == "libsvm"
            backend.decode_libsvm(paths[1], case["recipe"]; compression=compressions[1])
        else
            backend.decode_libsvm_split(paths..., case["recipe"];
                train_compression=compressions[1], test_compression=compressions[2])
        end
    end
end

function caught_type(f)
    try
        f()
        return nothing
    catch error
        return typeof(error)
    end
end

@testset "native ABI and independent shared corpus" begin
    @test ccall(Datamonger._native_symbol(:dm_abi_version), UInt32, ()) == 1
    for case in read_json("conformance", "cases.json")["cases"]
        for compressions in (("none", "none"), ("gzip", "bzip2"), ("bzip2", "gzip"))
            compare_decoded(decode_case(Datamonger, case; compressions),
                            decode_case(Reference, case; compressions))
        end
    end
    for case in read_json("conformance", "malformed.json")["cases"]
        for compression in ("none", "gzip", "bzip2")
            compressions = (compression, compression)
            @test caught_type(() -> decode_case(Datamonger, case; compressions)) ==
                  caught_type(() -> decode_case(Reference, case; compressions)) == DecodeError
        end
    end
    for case in read_json("conformance", "canonical", "cases.json")["cases"]
        component = Reference.component_from_descriptor(case["component"])
        @test Datamonger.canonical_bytes([component]) == Reference.canonical_bytes([component])
    end
end

@testset "generated native differential inputs" begin
    cases = read_json("conformance", "cases.json")["cases"]
    recipe = deepcopy(cases[1]["recipe"])
    recipe["columns"] = [Dict("name" => "δ", "type" => "float64"),
                         Dict("name" => "integer", "type" => "int64"),
                         Dict("name" => "text", "type" => "string"),
                         Dict("name" => "flag", "type" => "bool")]
    recipe["missing_values"] = ["NA"]
    floats = ["-0", "-0e-999", "5e-324", "2.2250738585072014e-308",
              "1.7976931348623157e308", "9007199254740993", "0.1", "-2.5e+17"]
    mktempdir() do directory
        for n in 0:24
            io = IOBuffer()
            print(io, "δ,integer,text,flag\r\n")
            for i in 1:n
                f = floats[mod1(i, length(floats))]
                integer = isodd(i) ? string(typemin(Int64) + i) : string(typemax(Int64) - i)
                text = i % 3 == 0 ? "NA" : "\"row $i, \"\"λ\"\"\0\""
                print(io, "$f,$integer,$text,$(isodd(i) ? "true" : "false")\r\n")
            end
            body = take!(io)
            svm = join(["$(isodd(i) ? "+1" : "-1") 1:$(i).5 4:-$(i)e-2\n" for i in 1:n])
            for compression in ("none", "gzip", "bzip2")
                path = joinpath(directory, "δ-$n")
                write(path, compression == "none" ? body : compressed_bytes(body, compression))
                compare_decoded(Datamonger.decode_delimited(path, recipe; compression),
                                Reference.decode_delimited(path, recipe; compression))
                svm_bytes = Vector{UInt8}(codeunits(svm))
                write(path, compression == "none" ? svm_bytes : compressed_bytes(svm_bytes, compression))
                compare_decoded(Datamonger.decode_libsvm(path, cases[3]["recipe"]; compression, prefix="λ_"),
                                Reference.decode_libsvm(path, cases[3]["recipe"]; compression, prefix="λ_"))
            end
        end
        wide = deepcopy(cases[3]["recipe"])
        wide["feature_count"] = 9007199254740991
        path = joinpath(directory, "wide")
        write(path, "+1 9007199254740991:1\n")
        compare_decoded(Datamonger.decode_libsvm(path, wide), Reference.decode_libsvm(path, wide))
        @test Datamonger.decode_libsvm(path, wide).data.features[1, wide["feature_count"]] == 1.0
    end
end

@testset "native failures and compression parity" begin
    cases = read_json("conformance", "cases.json")["cases"]
    recipe = cases[1]["recipe"]
    body = read(joinpath(FIXTURES, "conformance", cases[1]["input"]))
    mktempdir() do directory
        path = joinpath(directory, "compressed")
        for compression in ("gzip", "bzip2")
            encoded = compressed_bytes(body, compression)
            for invalid in (UInt8[], encoded[1:5], encoded[1:end-1], UInt8[0xff, 0x00])
                write(path, invalid)
                @test caught_type(() -> Datamonger.decode_delimited(path, recipe; compression)) ==
                      caught_type(() -> Reference.decode_delimited(path, recipe; compression)) == DecodeError
            end
            split_at = length(body) ÷ 2
            write(path, vcat(compressed_bytes(body[1:split_at], compression),
                             compressed_bytes(body[split_at+1:end], compression)))
            compare_decoded(Datamonger.decode_delimited(path, recipe; compression),
                            Reference.decode_delimited(path, recipe; compression))
            # Native decompression must retain the original stream's treatment
            # of member boundaries, padding, and trailing data.
            for suffix in (UInt8[0], UInt8[0xff], compressed_bytes(UInt8[], compression))
                write(path, vcat(encoded, suffix))
                actual = caught_type(() -> Datamonger.decode_delimited(path, recipe; compression))
                expected = caught_type(() -> Reference.decode_delimited(path, recipe; compression))
                @test actual == expected
                if actual === nothing
                    compare_decoded(Datamonger.decode_delimited(path, recipe; compression),
                                    Reference.decode_delimited(path, recipe; compression))
                end
            end
        end
        numeric_recipe = deepcopy(recipe)
        numeric_recipe["columns"] = [Dict("name" => "x", "type" => "float64")]
        for number in ("1e-999", "-1e-999")
            write(path, "x\n$number\n")
            @test_throws DecodeError Datamonger.decode_delimited(path, numeric_recipe)
            @test_throws DecodeError Reference.decode_delimited(path, numeric_recipe)
            svm = deepcopy(cases[3]["recipe"])
            svm["label_type"] = "float64"
            write(path, "$number 1:1\n")
            @test_throws DecodeError Datamonger.decode_libsvm(path, svm)
            @test_throws DecodeError Reference.decode_libsvm(path, svm)
        end
        absent = joinpath(directory, "absent")
        @test_throws DecodeError Datamonger.decode_delimited(absent, recipe)
        @test_throws UnsupportedDecoderError Datamonger.decode_delimited(absent, recipe; compression="xz")
        invalid = deepcopy(recipe)
        invalid["header"] = false
        @test_throws UnsupportedDecoderError Datamonger.decode_delimited(absent, invalid)
    end
end

@testset "native result lifetime and canonical validity" begin
    cases = read_json("conformance", "cases.json")["cases"]
    retained = [decode_case(Datamonger, cases[mod1(i, length(cases))]) for i in 1:24]
    GC.gc(true)
    for (i, decoded) in enumerate(retained)
        compare_decoded(decoded, decode_case(Reference, cases[mod1(i, length(cases))]))
    end
    for n in (0, 1, 7, 8, 9, 63, 64, 65)
        valid = BitVector([i % 3 != 0 for i in 1:n])
        components = (
            Datamonger.LogicalVector("float", "float64", [isodd(i) ? -0.0 : NaN for i in 1:n], valid),
            Datamonger.LogicalVector("bool", "bool", trues(n), valid),
            Datamonger.LogicalVector("int", "int64", fill(typemin(Int64), n), valid),
            Datamonger.LogicalVector("str", "string", fill("λ\0", n), valid),
            Datamonger.LogicalDenseMatrix("dense", "float64", 1, n, fill(-0.0, n), valid),
        )
        compare_components(components, components)
    end
    duplicate = Datamonger.LogicalVector("x", "bool", [true], [true])
    @test_throws DecodedIntegrityError Datamonger.canonical_bytes([duplicate, duplicate])
    bad_utf8 = Datamonger.LogicalVector("x", "string", [String(UInt8[0xff])], [true])
    @test_throws DecodedIntegrityError Datamonger.canonical_bytes([bad_utf8])
    @test_throws ErrorException Datamonger._with_native_result(_ -> error("callback"), C_NULL)
end
