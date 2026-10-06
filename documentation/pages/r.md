# R guide

Install the client from the Datamonger checkout, starting at the repository root:

```r
install.packages("packages/r", repos = NULL, type = "source")
```

Inspect dataset metadata before fetching data:

```r
library(datamonger)

info <- data_info("iris", source = "uci", version = "1")
print(info)
iris <- fetch_data("iris", source = "uci", version = "1")
```

The default registry index is bundled. Fetching an uncached dataset needs
network access. Record an explicit dataset version and a strong registry
selector for reproducibility, and check dataset license and provenance metadata.

The complete client guide below documents the public API.

See the [complete R client guide](https://github.com/jolars/datamonger/blob/main/packages/r/README.md)
for return types, registry selection, offline use, and cache management.

Return to the [Datamonger overview](index.md).
