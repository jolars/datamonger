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
still requires network access. The active registry is selected, in descending
precedence, by a `registry=` argument, a session setting, the nearest project
selector, and finally `BUNDLED_REGISTRY`. Updates are always explicit—none of
these scopes resolves a floating release name.

To discover a published selector by its bare release name, make an explicit
catalog lookup:

```python
from datamonger import fetch_data, resolve_registry

registry = resolve_registry("2026.09")
print(registry.index_sha256)
iris = fetch_data("iris", source="uci", registry=registry)
```

`resolve_registry()` reads the mutable catalog over HTTPS and returns a frozen
`Registry` containing the resolved release, index digest, and index URL. The
lookup is trusted only as strongly as that TLS session. Record and reuse the
returned selector when reproducibility matters; looking up the same bare name
again is not a cryptographic pin. The API accepts a custom HTTPS `catalog_url`
for alternate registries. It does not support floating aliases such as
`latest`.

Pass a `Registry` for one call when the selection belongs to one operation:

```python
from datamonger import Registry, fetch_data

registry = Registry(
    release="2026.08",
    index_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    index_url="https://registry.example/2026.08/index.json",
)
iris = fetch_data("iris", source="uci", registry=registry)
```

Use `set_registry(registry)` to keep that selector active for the Python
session, and use `set_registry(None)` to clear it. `active_registry()` reports
the selector that an unqualified call would use:

```python
from datamonger import active_registry, set_registry

set_registry(registry)
assert active_registry() == registry
set_registry(None)
```

To pin a project, check the selector into `.datamonger/selector.json` at the
project root:

```json
{
  "release": "2026.08",
  "index_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "index_url": "https://registry.example/2026.08/index.json"
}
```

Datamonger searches from the current working directory toward the filesystem
root and uses the nearest such file. A malformed project selector is an error;
it never causes a fallback to another registry. The release and digest form the
strong selector. The URL is only its retrieval location, and possession of a
digest authenticates nothing beyond the channel from which the selector came.

Delimited text returns a pandas data frame. LIBSVM returns a frozen
`SparseDataset` containing a SciPy CSR feature matrix and a NumPy response
vector. Pandas, NumPy, and SciPy are required dependencies, so these return
types never depend on which optional packages happen to be installed.

Use `return_info=True` to receive a `FetchResult` containing the resolved
dataset identity, registry selector, artifact digests, and decoded-verification
record.
