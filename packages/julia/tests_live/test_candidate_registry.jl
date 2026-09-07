using Datamonger
using JSON3

repository_root = normpath(joinpath(@__DIR__, "..", "..", ".."))
release_root = joinpath(repository_root, "registry", "releases", "candidate-0002")
selector_document = JSON3.read(
    read(joinpath(release_root, "selector.json")),
    Dict{String,Any},
)
index = JSON3.read(read(joinpath(release_root, "index.json")), Dict{String,Any})
selected = Datamonger.Registry(
    selector_document["release"],
    selector_document["index_sha256"],
    selector_document["index_url"],
    selector_document["schema_version"],
)
cache_dir = mktempdir(; prefix="datamonger-candidate-0002-")

for dataset in index["datasets"]
    result = fetch_data(
        dataset["name"];
        source=dataset["source"],
        version=dataset["version"],
        registry=selected,
        cache_dir,
        return_info=true,
    )
    records = dataset["representation"]["expect"]["verification"]
    expected = last(records)["digest"]
    result.info.canonical_digest == expected ||
        error("canonical digest mismatch for $(result.info.dataset_id)")
    println(result.info.dataset_id, " ", result.info.canonical_digest)
end
