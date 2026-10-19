# An offline data workflow in Julia

A reproducible data workflow needs more than a dataset name. It needs an exact
version, the records that describe that version, and a check that the retrieved
bytes decode into the expected values. This tutorial follows those steps with
the Julia client, then shows how to inspect and clean its cache.

The examples use small fixtures shipped in the repository checkout. They run
entirely offline in temporary directories, so running the walkthrough
neither contacts dataset hosts nor changes your normal cache. The final section
shows the corresponding calls for public datasets.

## Run the walkthrough

From the repository root, activate and prepare the Julia package:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()
include("tools/dm_julia_core.jl")
```

The remaining code blocks through the offline cache-miss example can be run in
order in one Julia session. The final section uses public dataset hosts and
requires network access.

## Inspect the available data

Load Datamonger and choose a private cache directory for the walkthrough:

```julia
using Datamonger
using DataFrames
using SparseArrays
using SHA
using JSON3

cache = mktempdir()
registry = BUNDLED_REGISTRY
available = list_data(; registry, cache_dir=cache, offline=true)
sort([info.dataset_id for info in available])
```

`list_data` reads registry metadata. It does not download dataset artifacts.
Passing the bundled selector explicitly also makes this example independent of
any session selector or project configuration in your checkout.

Inspect one record before deciding to retrieve its data:

```julia
iris_info = data_info("uci:iris@1"; registry, cache_dir=cache, offline=true)
(
    title=iris_info.title,
    license=iris_info.license["identifier"],
    provider=iris_info.provenance["provider"],
    decoder=iris_info.representation["decoder"],
)
```

The record includes the source's provenance, license information, tasks, expected
components, and verification records. A missing or unknown license is useful
information to investigate; registry inclusion itself grants no usage rights.

## Prepare an offline example

The repository includes a tiny CSV with floating-point measurements, integer
counts, text labels, and Boolean flags. Its registry record is part of the
shared conformance corpus used by the language clients. Find the fixtures
relative to the installed checkout:

```julia
fixtures = joinpath(pkgdir(Datamonger), "test", "fixtures")
selector = JSON3.read(
    read(joinpath(fixtures, "registry", "selector.json")),
    Dict{String,Any},
)
example_registry = Registry(
    selector["release"],
    selector["index_sha256"],
    selector["index_url"],
)
```

An offline fetch needs both the selected index and its artifacts in the cache.
For this self-contained demonstration, copy the checked-in files to their
content-addressed locations. Normal online calls populate these locations for
you; manual cache preparation is only needed for this fixture walkthrough.

```julia
registry_directory = joinpath(cache, "registries", "sha256")
artifact_directory = joinpath(cache, "objects", "sha256")
mkpath(registry_directory)
mkpath(artifact_directory)
cp(
    joinpath(fixtures, "registry", "index.json"),
    joinpath(registry_directory, example_registry.index_sha256),
)
for path in readdir(joinpath(fixtures, "conformance", "artifacts"); join=true)
    digest = bytes2hex(sha256(read(path)))
    cp(path, joinpath(artifact_directory, digest))
end
```

The filenames are SHA-256 digests. Copying a file into the cache does not make it
trusted: Datamonger still verifies its bytes before using it. The fixture
registry's download addresses are placeholders, and `offline=true` forbids any
attempt to contact them.

## Fetch and verify a table

Request both the decoded data and its reproducibility metadata:

```julia
result = fetch_data(
    "conformance:mixed_csv@1";
    registry=example_registry,
    cache_dir=cache,
    offline=true,
    return_info=true,
)
table = result.data
@assert table isa DataFrame
@assert size(table) == (5, 4)
table
```

The table has five rows and four columns. The result separates the analysis
object, `result.data`, from the fetch record,
`result.info`. Delimited data becomes a `DataFrame`, and column names come from
the registry recipe. The CSV decoder handles quoting, escaped quotes, and
missing fields according to that recipe.

```julia
(
    dataset=result.info.dataset_id,
    release=result.info.registry_release,
    verification=result.info.verification,
    canonical_digest=result.info.canonical_digest,
)
```

The `:decoded` verification status means that artifact hashes, decoded shapes,
and the canonical logical digest all passed. The canonical digest describes
the logical values rather than a language's in-memory representation.

`verify_decoded=false` skips shape and canonical verification and reports
`:artifact` instead. It still verifies artifact bytes. Keep the default unless
you have a specific reason to skip the decoded checks.

## Work with missing values and exact integers

Datamonger preserves column types. A column with missing values uses
`Union{Missing,T}` rather than converting everything to text or floating point:

```julia
[(name, eltype(table[!, name])) for name in names(table)]
```

Use Julia's usual missing-value operations when computing summaries. For
example, the measurement column has four observed values:

```julia
measurements = collect(skipmissing(table.measurement))
@assert length(measurements) == 4
sum(measurements) / length(measurements)
```

Counts remain exact `Int64` values. Boolean values remain Boolean, and quoted
commas and quotation marks remain part of the decoded strings. Datamonger does
not impute missing observations or transform variables for a model.

## Retrieve sparse data and train/test splits

LIBSVM and SVMLight representations return a `SparseDataset` with `features`
and `response` fields:

```julia
sparse_data = fetch_data(
    "conformance:small_libsvm@1";
    registry=example_registry,
    cache_dir=cache,
    offline=true,
)
@assert sparse_data isa SparseDataset
(
    shape=size(sparse_data.features),
    stored_values=nnz(sparse_data.features),
    response=sparse_data.response,
)
```

The feature matrix normally uses `SparseMatrixCSC`. Exceptionally wide data
uses the read-only `CSRMatrix` type to avoid allocating an impractical number
of column pointers. Both provide matrix indexing, `size`, and `nnz`; check the
concrete type before assuming a downstream solver supports it. Responses keep
the recipe's exact integer or floating-point type.

A registry can also describe an explicit training and test pair:

```julia
split = fetch_data(
    "conformance:small_libsvm_split@1";
    registry=example_registry,
    cache_dir=cache,
    offline=true,
)
@assert split isa SparseDatasetSplit
(train=size(split.train.features), test=size(split.test.features))
```

A `SparseDatasetSplit` preserves the published split. Datamonger does not
shuffle observations or choose a new split for you.

## Inspect artifact bytes and cache contents

Use `fetch_artifact` when another tool needs the source file rather than a Julia
object. It returns a path to verified cached bytes:

```julia
artifact_path = fetch_artifact(
    "conformance:mixed_csv@1";
    registry=example_registry,
    cache_dir=cache,
    offline=true,
)
read(artifact_path, String)
```

Treat that path as cache-owned. Copy it elsewhere if it needs to outlive cache
cleaning, and avoid editing its contents in place.

`cache_info` inventories entries and verifies their stored hashes without
accessing the network:

```julia
inventory = cache_info(; cache_dir=cache)
@assert all(entry.valid for entry in inventory.entries)
(
    entries=length(inventory.entries),
    bytes=inventory.total_size,
    all_valid=all(entry.valid for entry in inventory.entries),
)
```

Each entry identifies its kind, digest, size, path, modification time, validity,
and known dataset associations. The tutorial copied extra conformance files,
including malformed examples used by tests. A valid cache entry means its bytes
match its filename; it does not mean every file is a decodable dataset.

Eviction is manual. Select a dataset to remove its associated inactive artifacts:

```julia
removed = cache_clean(; dataset="conformance:mixed_csv@1", cache_dir=cache)
@assert !isempty(removed.removed)
(bytes_removed=removed.bytes_removed, entries_removed=length(removed.removed))
```

Files shared with another representation refer to the same cached object, so
removing one can affect later offline calls for those representations too.
The `older_than` filter can restrict eviction by age, for example
`cache_clean(; older_than=Day(30), cache_dir=cache)` after `using Dates`.
When both filters are supplied, they intersect. Active readers and publishers
are skipped. Calling `cache_clean` without filters selects the whole cache.

## Recognize an offline cache miss

The CSV artifact has now been removed. Repeating its offline fetch produces an
`OfflineError` rather than silently accessing the network:

```julia
try
    fetch_data(
        "conformance:mixed_csv@1";
        registry=example_registry,
        cache_dir=cache,
        offline=true,
    )
    error("Expected an offline cache miss")
catch exception
    @assert exception isa OfflineError
    println(nameof(typeof(exception)))
end
rm(cache; recursive=true)
```

A missing registry index raises `RegistryOfflineError`. Integrity failures,
unsupported decoders, and unknown datasets have distinct exception types too.
Catch the types your application can handle, and let unexpected failures
propagate. The [client guide](https://github.com/jolars/datamonger/blob/main/packages/julia/README.md#error-taxonomy-and-cache-management) summarizes
the error categories.

## Use the same workflow with public datasets

For a real analysis, use the bundled stable registry or another recorded strong
selector. These calls require access to upstream hosts when artifacts are not cached:

```julia
using Datamonger

registry = BUNDLED_REGISTRY
result = fetch_data("uci:iris@1"; registry, return_info=true)
iris = result.data
heart = fetch_data("libsvm:heart_scale@1"; registry)
```

Keep `result.info.dataset_id`, `result.info.registry_release`,
`result.info.registry_index_sha256`, and `result.info.canonical_digest` with the
analysis. Later, reuse the same dataset reference and selector; use
`offline=true` when the run must rely entirely on previously cached inputs.
See [Registries and reproducibility](reproducibility.md) for project selectors,
selection precedence, and the limits of catalog discovery.
