# Julia guide

Install the client from the Datamonger checkout, starting at the repository root:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()
include("tools/dm_julia_core.jl")
```

Inspect dataset metadata before fetching data:

```julia
using Datamonger

info = data_info("uci:iris@1")
iris = fetch_data("uci:iris@1")
```

Dataset operations also accept separate arguments, such as
`fetch_data("iris"; source="uci", version="1")`. Omit `source` for qualified
references and omit `version` when the reference embeds it. Duplicate arguments
raise an error even when the values agree. `"uci:iris"` selects the registry's
declared default version.

The default registry index is bundled. Fetching an uncached dataset needs
network access. Record an explicit dataset version and a strong registry
selector for reproducibility, and check dataset license and provenance metadata.

Use the Julia section in the navigation bar to browse the extracted API reference,
including the generated error types. Function overviews show method documentation
and link equivalent operations across the three language clients.

See the [complete Julia client guide](https://github.com/jolars/datamonger/blob/main/packages/julia/README.md)
for return types, registry selection, offline use, and cache management.

For a longer worked example, follow the
[offline data workflow](../../packages/julia/tutorials/offline-workflow.md), then
read about [registries and reproducibility](../../packages/julia/tutorials/reproducibility.md).

Return to the [Datamonger overview](index.md).
