# R guide

Install the client from the Datamonger checkout, starting at the repository root:

```r
install.packages("packages/r", repos = NULL, type = "source")
```

Inspect dataset metadata before fetching data:

```r
library(datamonger)

info <- data_info("uci:iris@1")
print(info)
iris <- fetch_data("uci:iris@1")
```

Dataset operations also accept separate arguments, such as
`fetch_data("iris", source = "uci", version = "1")`. Omit `source` for qualified
references and omit `version` when the reference embeds it. Duplicate arguments
raise an error even when the values agree. `"uci:iris"` selects the registry's
declared default version.

The default registry index is bundled. Fetching an uncached dataset needs
network access. Record an explicit dataset version and a strong registry
selector for reproducibility, and check dataset license and provenance metadata.

The complete client guide below documents the public API.

See the [complete R client guide](https://github.com/jolars/datamonger/blob/main/packages/r/README.md)
for return types, registry selection, offline use, and cache management.

Return to the [Datamonger overview](index.md).
