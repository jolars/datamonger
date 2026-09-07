# Datamonger

Datamonger is a cross-language registry and artifact system for retrieving,
verifying, and identically decoding public research datasets. A registry record
fixes the source bytes, the decoding recipe, the expected shape, and a digest of
the decoded logical values. A strong registry selector fixes the complete set of
records used by an analysis.

Datamonger is pre-release software. Specification release candidate
`spec-v1-rc1` freezes the revision 1 feature set. The Python reference client and
the independent R and Julia clients implement it, pass the shared conformance
suite, and reproduce all ten candidate canonical verification records. Stable
publication and coordinated client releases remain. The paired ten-dataset
`candidate-0002` registry is a prerelease; its verification records are
provisional, and all of its artifacts remain upstream-only.

## What Datamonger verifies

Datamonger keeps several distinct claims separate:

- A strong selector identifies exact registry-index bytes.
- Each registry record identifies exact artifact bytes by size and SHA-256.
- A versioned canonical digest checks the decoded logical values and their
  structure.
- Provenance, license, distribution, and preservation fields describe where the
  data came from and what the registry is permitted and able to provide.

A digest provides integrity relative to the channel that supplied it. It does
not authenticate a selector obtained from an untrusted source, grant permission
to use a dataset, or preserve an upstream-only artifact. See [TRUST.md](TRUST.md)
for the trust model and its limits.

## Try the Python client

The package has not yet been published to PyPI. Install it from a checkout with
Python 3.11 or newer:

```console
python -m pip install ./packages/python
```

The bundled `proof-0001` registry works as an offline trust root for its index.
Dataset artifacts are downloaded on first use and then kept in a verified,
content-addressed cache:

```python
from datamonger import fetch_data

iris = fetch_data("iris", source="uci")
heart = fetch_data("heart_scale", source="libsvm")
```

Use an explicit version and request reproducibility metadata for an analysis:

```python
from datamonger import fetch_data

result = fetch_data("iris", source="uci", version="1", return_info=True)
print(result.info.dataset_id)
print(result.info.registry_release, result.info.registry_index_sha256)
print(result.info.artifact_digests)
print(result.info.canonical_form, result.info.canonical_digest)
```

Record the canonical dataset identifier, registry release, and index digest.
For a project that uses a registry other than the bundled snapshot, also check
the complete strong selector into `.datamonger/selector.json`. A bare release
name is only a TLS-trusted discovery mechanism; the returned selector becomes a
reproducible pin when it is recorded and reused.

Before using a dataset, inspect its provenance and license status:

```python
from datamonger import data_info

info = data_info("iris", source="uci", version="1")
print(info.dataset_id)
print(info.provenance)
print(info.license)
print([artifact["distribution"] for artifact in info.artifacts])
```

An unknown license remains unknown—registry inclusion is not legal advice or a
license grant. An `upstream-only` artifact is available only while an upstream
location or a local cache copy remains available.

The [Python package guide](packages/python/README.md) documents registry
selection, return types, metadata, verified artifact access, offline operation,
errors, and cache management.

## Try the R client

The R package is also pre-release and is not yet on CRAN. Install it from a
checkout, then make an explicit cache choice:

```r
install.packages("packages/r", repos = NULL, type = "source")
library(datamonger)

options(datamonger.cache_consent = TRUE)
iris <- fetch_data("iris", source = "uci")
```

Without consent, the R client uses the session temporary directory. Its
registry selection, verification, offline, metadata, artifact, and cache
management operations follow the same revision 1 contracts as the Python
client. See the [R package guide](packages/r/README.md) for R return types and
the cache-consent policy.

## Try the Julia client

Instantiate the pre-release Julia package from a checkout, then load it:

```julia
using Pkg
Pkg.activate("packages/julia")
Pkg.instantiate()

using Datamonger
iris = fetch_data("iris"; source="uci")
heart = fetch_data("heart_scale"; source="libsvm")
```

An explicit `cache_dir` grants permission to use that directory. Otherwise, set
`DATAMONGER_CACHE_CONSENT=true` to use the platform cache in noninteractive
work; without consent, the client uses a session-temporary directory. See the
[Julia package guide](packages/julia/README.md) for native return types and the
complete public API.

## Documentation

- [Python package guide](packages/python/README.md)—installation and public API
  behavior.
- [R package guide](packages/r/README.md)—installation, cache consent, and
  public API behavior.
- [Julia package guide](packages/julia/README.md)—installation, native return
  types, cache consent, and public API behavior.
- [Normative specification](spec/README.md)—the frozen revision 1 contracts for
  independent implementations.
- [Trust model](TRUST.md)—trust roots, guarantees, and non-guarantees.
- [Contributor guide](CONTRIBUTING.md)—code, specification, and dataset changes.
- [Operations runbook](OPERATIONS.md)—registry publication, canaries, and
  incident response.
- [Architecture](DESIGN.md)—design rationale and project scope.
- [Roadmap](TODO.md)—milestones and release status.

## Current registries

`candidate-0002` contains ten reviewed UCI and LIBSVM datasets spanning
regression, binary and multiclass classification, unsupervised data, dense and
sparse data, and a train/test split. Its selector is
[`registry/releases/candidate-0002/selector.json`](registry/releases/candidate-0002/selector.json).
All three client packages continue to bundle the smaller `proof-0001` snapshot
until the certified candidate is promoted to the first stable registry and the
coordinated releases adopt its selector.

The immutable releases under [`tests/registry`](tests/registry) and the
language-neutral corpus under [`tests/conformance`](tests/conformance) are for
implementation conformance, not end-user data analysis.

## Development

Enter the repository's devenv shell and run the same hermetic quality gate as
CI:

```console
devenv test
```

Network-dependent upstream verification is deliberately separate from this
gate. See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflows and
[OPERATIONS.md](OPERATIONS.md) for live verification and release procedures.
