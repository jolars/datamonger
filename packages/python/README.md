# Datamonger Python client

This package is the Python reference client for Datamonger's normative draft
contracts. Its public interfaces may change until specification revision 1 is
independently certified.

The client bundles the immutable `proof-0001` registry snapshot and verifies it
against a trusted digest shipped in the package. It is the default registry, so
the index remains available without network access:

```python
from datamonger import fetch_data

iris = fetch_data("iris", source="uci")
heart = fetch_data("heart_scale", source="libsvm")
```

Only the registry index is bundled; retrieving an uncached dataset artifact
still requires network access. The same trusted selector is available as
`BUNDLED_REGISTRY` when an application needs to record or pass it explicitly:

```python
from datamonger import BUNDLED_REGISTRY, fetch_data

iris = fetch_data("iris", source="uci", registry=BUNDLED_REGISTRY)
```

Delimited text returns a pandas data frame. LIBSVM returns a frozen
`SparseDataset` containing a SciPy CSR feature matrix and a NumPy response
vector. Pandas, NumPy, and SciPy are required dependencies, so these return
types never depend on which optional packages happen to be installed.

Use `return_info=True` to receive a `FetchResult` containing the resolved
dataset identity, registry selector, artifact digests, and decoded-verification
record.
