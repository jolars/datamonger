# Datamonger Python client

This package is the provisional Python reference client for Datamonger. Its
interfaces and wire formats may change until specification revision 1 is
independently certified.

The slice 0A API requires an explicit strong registry selector:

```python
from datamonger import Registry, fetch_data

registry = Registry(
    release="proof-0001",
    index_sha256="<64 lowercase hexadecimal characters>",
    index_url="https://example.org/index.json",
)

data = fetch_data("mixed", source="fixture", registry=registry)
```

Use `return_info=True` to receive a `FetchResult` containing the resolved
dataset identity, registry selector, artifact digests, and decoded-verification
record.
