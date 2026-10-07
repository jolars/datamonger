# Python guide

Install the client from the Datamonger checkout, starting at the repository root:

```console
python -m pip install ./packages/python
```

Inspect dataset metadata before fetching data:

```python
from datamonger import data_info, fetch_data

info = data_info("uci:iris@1")
print(info.license)
result = fetch_data("uci:iris@1", return_info=True)
print(result.info.dataset_id)
print(result.info.registry_release, result.info.registry_index_sha256)
print(result.info.canonical_digest)
```

Dataset operations also accept separate arguments, such as
`fetch_data("iris", source="uci", version="1")`. Omit `source` for qualified
references and omit `version` when the reference embeds it. Duplicate arguments
raise an error even when the values agree. `"uci:iris"` selects the registry's
declared default version.

The default registry index is bundled. Fetching an uncached dataset needs
network access. Record an explicit dataset version and a strong registry
selector for reproducibility, and check dataset license and provenance metadata.

The complete client guide below documents the public API.

See the [complete Python client guide](https://github.com/jolars/datamonger/blob/main/packages/python/README.md)
for return types, registry selection, offline use, and cache management.

Return to the [Datamonger overview](index.md).
