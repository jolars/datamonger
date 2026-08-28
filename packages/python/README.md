# Datamonger Python client

This package is the provisional Python reference client for Datamonger. Its
interfaces and wire formats may change until specification revision 1 is
independently certified.

The vertical-proof API requires an explicit strong registry selector:

```python
from datamonger import Registry, fetch_data

registry = Registry(
    release="proof-0001",
    index_sha256="98cdbc7c8c795dcd021775de4c955c2442e6e1f2d7911e4c53b72327d90f6578",
    index_url=(
        "https://github.com/jolars/datamonger/releases/download/"
        "registry-proof-0001/index.json"
    ),
)

iris = fetch_data("iris", source="uci", registry=registry)
heart = fetch_data("heart_scale", source="libsvm", registry=registry)
```

Delimited text returns a pandas data frame. LIBSVM returns a frozen
`SparseDataset` containing a SciPy CSR feature matrix and a NumPy response
vector. Pandas, NumPy, and SciPy are required dependencies, so these return
types never depend on which optional packages happen to be installed.

Use `return_info=True` to receive a `FetchResult` containing the resolved
dataset identity, registry selector, artifact digests, and decoded-verification
record.
