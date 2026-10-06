# Julia guide

Install the client from the Datamonger checkout, starting at the repository root:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()
```

Inspect dataset metadata before fetching data:

```julia
using Datamonger

info = data_info("iris"; source="uci", version="1")
iris = fetch_data("iris"; source="uci", version="1")
```

The default registry index is bundled. Fetching an uncached dataset needs
network access. Record an explicit dataset version and a strong registry
selector for reproducibility, and check dataset license and provenance metadata.

This prototype provides an authored Julia guide. Diplodocus does not yet
extract Julia API documentation.

See the [complete Julia client guide](https://github.com/jolars/datamonger/blob/main/packages/julia/README.md)
for return types, registry selection, offline use, and cache management.

Return to the [Datamonger overview](index.md).
