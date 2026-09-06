# Datamonger Python client

This package is the Python reference client for Datamonger's feature-frozen
revision 1 contracts. Its public interfaces may change until specification
revision 1 is independently certified.

## Installation and status

The package requires Python 3.11 or newer and has not yet been published to
PyPI. Install it from the repository root with:

```console
python -m pip install ./packages/python
```

For development, enter the repository's devenv shell and use the locked
environment documented in the
[contributor guide](https://github.com/jolars/datamonger/blob/main/CONTRIBUTING.md).

The package requires pandas, NumPy, SciPy, platformdirs, and portalocker. The
project code is MIT-licensed; datasets retain their own licenses and terms. See
the repository's
[trust model](https://github.com/jolars/datamonger/blob/main/TRUST.md) before
relying on registry license, distribution, or preservation metadata.

## Quick start

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

For a reproducible analysis, pass an explicit dataset `version` and use
`return_info=True`. Retain the resolved `dataset_id`, `registry_release`,
`registry_index_sha256`, artifact digests, verification level, canonical-form
version, and canonical digest.

## Registry selection

To discover a published selector by its bare release name, make an explicit
catalog lookup:

```python
from datamonger import fetch_data, resolve_registry

registry = resolve_registry("candidate-0001")
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
  "schema_version": 1,
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

## Return types and decoded verification

The decoded return type is fixed by the representation:

| Representation | Artifact formats | Python return type |
| --- | --- | --- |
| `delimited-text` | CSV or TSV | `pandas.DataFrame` |
| `libsvm` | LIBSVM or SVMLight | `SparseDataset` |
| `libsvm-split` | LIBSVM or SVMLight | `SparseDatasetSplit` |

Delimited frames use pandas' nullable `Float64`, `Int64`, `string`, and
`boolean` dtypes, according to the declared logical column types. A frozen
`SparseDataset` record contains a float64 SciPy CSR `features` matrix and an
int64 or float64 NumPy `response` vector, according to `label_type`. A frozen
`SparseDatasetSplit` has separate `train` and `test` fields containing those
same records, so neither input is concatenated or discarded. The public
`DatasetData` type alias is the union of these three return types.

`return_info=True` wraps the same decoded object in `FetchResult.data`; it does
not change its representation. Pandas, NumPy, and SciPy are required
dependencies, so return types never depend on which optional packages happen
to be installed.

CSV, TSV, LIBSVM, and SVMLight artifacts support manifest-declared `none`,
`gzip`, and `bzip2` compression. The client verifies and caches the exact
compressed artifact, then decompresses it for decoding; file names and URLs do
not determine the compression method.

Use `return_info=True` to receive a `FetchResult` containing the resolved
dataset identity, registry selector, artifact digests, and decoded-verification
record. Decoded verification is enabled by default for every representation.
It checks both the expected component shapes and the canonical SHA-256. For
diagnostic or performance-sensitive work, `verify_decoded=False` explicitly
skips those checks while retaining mandatory artifact size and SHA-256
verification; `FetchInfo.verification` then reports `"artifact"` rather than
`"decoded"`.

## Metadata and artifact access

Inspect registry metadata without retrieving an artifact with `data_info()`, or
enumerate every version in the active immutable release with `list_data()`:

```python
from datamonger import data_info, list_data

iris_info = data_info("iris", source="uci")
assert iris_info.dataset_id == "uci:iris@1"
for info in list_data():
    print(info.dataset_id, info.modality, info.representation["expect"])
```

Both operations use the same registry selection as `fetch_data()`, and
`data_info()` uses its default-version resolution. A `DataInfo` includes the
registry selector, provenance, licensing, artifacts and their distribution and
preservation records, the full representation, `expected_components`,
`verification_records`, related datasets, and task metadata. Pass
`offline=True` to require a bundled or already cached registry index.

To retrieve verified artifact bytes without decoding them, use
`fetch_artifact()`:

```python
from datamonger import fetch_artifact

iris_csv = fetch_artifact("iris", source="uci")
```

The function returns a `pathlib.Path` in the content-addressed cache. An
artifact name may be omitted only when the resolved dataset version has one
artifact; otherwise, pass it explicitly with `artifact="train"`. Retrieval
locations are tried in manifest order, and size and SHA-256 verification cannot
be disabled. The cached bytes retain any artifact compression declared by the
manifest—HTTP content coding is a separate transport detail.

Pass `offline=True` to `fetch_data()` or `fetch_artifact()` when network access
must not be attempted. The selected registry does not change in offline mode.
Remote registry indexes and artifacts must already be present and valid in the
cache; the package's bundled registry index remains available, but its dataset
artifacts are not bundled. Missing or corrupt cached content raises
`RegistryOfflineError` for an index and `OfflineError` for an artifact.

## Error taxonomy

Expected failures derive from `DatamongerError` and are exported by
`datamonger.errors`. The shared semantic categories map to Python as follows:

| Category | Python type |
| --- | --- |
| `unknown-dataset` | `UnknownDatasetError` |
| `unsupported-registry` | `UnsupportedRegistryError` |
| `unsupported-decoder` | `UnsupportedDecoderError` |
| `artifact-unavailable` | `ArtifactUnavailableError` |
| `artifact-offline` | `OfflineError` |
| `retrieval-exhausted` | `RetrievalLocationsError` |
| `artifact-integrity` | `ArtifactIntegrityError` |
| `decoded-integrity` | `DecodedIntegrityError` |
| `cache` | `CacheError` |
| `decode` | `DecodeError` |

All artifact selection and retrieval failures derive from `RetrievalError`.
`ArtifactSelectionError` additionally distinguishes an omitted, ambiguous, or
unknown artifact name. `RegistryError` is the base for
`RegistryIntegrityError`, `RegistryOfflineError`, `RegistryReleaseError`, and
`RegistryRetrievalError`; `UnsupportedRegistryError` is also a registry failure.

## Cache management

Inspect the cache with `cache_info()`:

```python
from datamonger import cache_info

info = cache_info()
print(info.location, info.total_size)
for entry in info.entries:
    print(entry.kind, entry.sha256, entry.size, entry.datasets, entry.valid)
```

The inventory covers cached registry indexes and artifacts, hashes every entry,
and associates artifact digests with canonical dataset versions found in the
bundled and cached indexes. Use `cache_clean(dataset="uci:iris@1")` to remove
the artifacts referenced by one version, or use `older_than=timedelta(days=30)`
to remove old entries. The two filters intersect when combined. Calling
`cache_clean()` without filters selects the entire cache. Its result lists both
removed entries and entries skipped because another process is publishing or
reading them. Cache eviction is always explicit; the client never evicts data
automatically.

Every public operation that reads or changes the cache accepts `cache_dir=`.
Pass the same private directory consistently to isolate an application or test.
The platform-default location is reported by `cache_info().location`.

## Cache coordination

The Python client coordinates each cached registry and artifact through an
operating-system file lease at
`.leases/<namespace>/sha256/<digest>.lock`. Publishers and readers take shared
leases. A cleaner tries the exclusive side without waiting and skips the object
when that attempt fails. A separate `<digest>.publish.lock` serializes the brief
validation and commit phases while allowing downloads for the same digest to
overlap.

Downloads remain in destination-directory `.download-*` files until they have
been flushed, size-checked, and hash-checked. Publication uses an atomic rename,
and a publisher rechecks the target under the publication lock so that it does
not replace a complete object committed by another publisher. Readers retain
their shared lease through registry parsing or dataset decoding.

Lease files deliberately remain on disk as rendezvous records. Their presence
does not indicate ownership; the operating system's lock state does. Process
termination releases that state, and a restarted host has no surviving lock
owners, so a stale record is immediately reclaimable without a timeout that
could misclassify a slow but live reader. The cache root is client-private and
must reside on a filesystem that implements local advisory file locking and
atomic replacement.

## Public API summary

| Name | Purpose |
| --- | --- |
| `fetch_data()` | Resolve, retrieve, verify, and decode one dataset. |
| `fetch_artifact()` | Retrieve one verified artifact without decoding it. |
| `data_info()` | Inspect metadata for one resolved dataset version. |
| `list_data()` | List every version in the selected registry. |
| `resolve_registry()` | Discover a strong selector through an HTTPS catalog. |
| `active_registry()` | Report the selector an unqualified call will use. |
| `set_registry()` | Set or clear the process-local session selector. |
| `cache_info()` | Inspect cached indexes and artifacts without network access. |
| `cache_clean()` | Explicitly evict matching inactive cache entries. |

The package also exports these public values and immutable result types:

| Name | Contents |
| --- | --- |
| `BUNDLED_REGISTRY` | The package's default strong selector. |
| `Registry` | A selector's release, index digest, URL, and schema version. |
| `FetchResult` | Decoded `data` and its `FetchInfo`. |
| `FetchInfo` | Resolved identity, selector, artifact digests, and verification record. |
| `DataInfo` | Provenance, license, artifacts, representation, expectations, relations, and tasks. |
| `SparseDataset` | A CSR feature matrix and response vector. |
| `SparseDatasetSplit` | Separate train and test `SparseDataset` records. |
| `DatasetData` | The union of all decoded return types. |
| `CacheEntry` | One inspected registry or artifact cache object. |
| `CacheInfo` | Cache location, total size, and entries. |
| `CacheCleanResult` | Removed and skipped entries, plus `bytes_removed`. |

Expected public failures are exported from `datamonger.errors`; all derive from
`DatamongerError`.
