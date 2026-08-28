# Datamonger Design

## Overview

Datamonger is a cross-language system for retrieving, caching, verifying, and loading public datasets reproducibly.

It provides clients for R, Python, and Julia with a shared registry of datasets.

Typical usage should be simple:

```r
x <- fetch_data("cadata", source = "libsvm")
```

```python
x = fetch_data("cadata", source="libsvm")
```

```julia
x = fetch_data("cadata"; source="libsvm")
```

The important property is that a registered dataset version refers to stable, verified data even if the original provider changes URLs, modifies files in place, or disappears.

Here, "verified" means that retrieved bytes and their interpretation match a
trusted registry release. SHA-256 provides integrity relative to that registry;
authenticating the registry itself is a separate concern.

Datamonger is therefore best thought of as a **dataset registry and artifact system with language-specific clients**, rather than merely a downloading library.

---

## Goals and non-goals

Datamonger should make public research datasets:

* easy to retrieve;
* reproducible;
* verifiable;
* locally cacheable;
* usable offline after retrieval;
* consistently identifiable across R, Python, and Julia;
* independent of fragile upstream URLs;
* explicit about provenance and licensing.

Datamonger is not intended to become another Kaggle, OpenML, or Hugging Face Hub. It should not require user accounts, provide arbitrary uploads, host models, perform remote computation, or become a general-purpose data publishing platform.

The central design principle is:

> A published dataset version identifies immutable artifacts.

URLs, mirrors, storage providers, and client implementations may change. The underlying artifact identity must not.

---

## Repository structure

Datamonger starts as a monorepo:

```text
datamonger/
├── DESIGN.md
├── README.md
├── LICENSE
├── CONTRIBUTING.md
│
├── registry/
│   ├── datasets/
│   │   ├── libsvm/
│   │   ├── uci/
│   │   └── openml/
│   ├── schema/
│   └── index/
│
├── packages/
│   ├── r/
│   ├── python/
│   └── julia/
│
├── tools/
└── tests/
    ├── fixtures/
    └── conformance/
```

There is no shared native implementation initially.

The R, Python, and Julia clients independently implement the logic required for
registry resolution, downloading, hashing, caching, and decoding.

Cross-language consistency is defined by the registry specification and shared conformance tests, not by shared implementation code.

The registry is the shared core of the system.

---

## Dataset identity

Dataset identity consists of three components:

```text
source
name
version
```

For example:

```text
source  = libsvm
name    = cadata
version = "1"
```

The primary user-facing API accepts these separately:

```r
fetch_data("cadata", source = "libsvm", version = "1")
```

This avoids forcing users to deal with a mini-language embedded in strings.

A canonical serialized identifier must nevertheless exist for manifests,
lockfiles, logs, URLs, and debugging. For example:

```text
libsvm:cadata@1
```

The registry specification must define this syntax normatively so all clients
serialize it identically. Initially, `source` and `name` use lowercase ASCII
identifiers matching `[a-z0-9][a-z0-9._-]*`. A version is an opaque ASCII
string matching `[A-Za-z0-9][A-Za-z0-9._+-]*`. Versions are case sensitive,
and clients must not infer version ordering from their spelling.

`source` is a stable registry namespace describing the provenance collection,
not the URL or mirror used to retrieve an artifact.

If `version` is omitted, the default version in the selected registry release
is used. This is a convenience query, not a reproducible identifier. Clients
must make the resolved canonical dataset identifier and registry release
visible through returned metadata, an optional `return_info`-style result, or
an equally explicit idiomatic mechanism.

A specific published version must never change meaning.

The identity-bearing fields of a dataset version are:

* its source, name, and version;
* the names, sizes, digests, formats, and compression of its artifacts;
* its modality and representation recipe;
* decoder names, decoder specification versions, inputs, and options;
* task definitions, when present.

Changing any identity-bearing field requires a new dataset version. Retrieval
locations and descriptive metadata, such as citations or license
clarifications, may be updated by a later registry release without changing
the dataset version. CI must compare new registry releases with published ones
and reject changes to identity-bearing fields; validating only the current
tree is insufficient.

---

## Data model

Datamonger distinguishes four concepts:

### Artifact

An artifact is an immutable sequence of bytes identified by a cryptographic digest.

Examples:

* a CSV file;
* a compressed LIBSVM file;
* a ZIP archive;
* a collection of image files stored in an archive.

Artifacts are the foundation of reproducibility.

### Representation

A representation is a deterministic recipe for decoding one or more artifacts
into logical data. It identifies its input artifacts, a versioned decoder
contract, and every option that can affect the result.

For example, a delimited-text representation specifies the character encoding,
delimiter, quoting and escaping rules, header handling, missing-value tokens,
and logical column types. A LIBSVM representation specifies the feature-index
base, feature count, label handling, and ordering rules.

The representation contract concerns logical values, names, shapes, and
ordering. Clients may use different native containers, integer widths, or
sparse-matrix implementations as long as those logical properties agree.

### Dataset

A dataset is the meaningful data obtained by applying a representation recipe
to one or more artifacts.

A dataset may be:

* tabular;
* a dense or sparse matrix;
* image data;
* text;
* a time series;
* graph data;
* audio;
* or another modality.

A dataset does not inherently need to have a response variable.

### Task

A task is an optional interpretation of a dataset for a statistical or machine-learning problem.

Examples:

```text
classification
regression
multilabel classification
```

A task may specify a target, features, predefined splits, or related information.

Tasks are metadata layered on top of datasets. They are not part of the fundamental definition of what a dataset is.

Nevertheless, a task definition published with a dataset version is frozen so
that its target and interpretation cannot drift. Until tasks acquire their own
versioned identities, adding or changing a task requires a new dataset version,
even when the artifact digests remain the same. Content-addressed storage still
deduplicates those unchanged artifacts.

This distinction allows the same system to represent supervised, unsupervised, image, text, and other forms of data without forcing everything into an `X, y` abstraction.

---

## Registry manifests

Each dataset version is represented by a human-readable manifest, initially using YAML.

For example:

```yaml
schema_version: 1

source: libsvm
name: cadata
version: "1"

title: California Housing
description: >
  California housing dataset distributed through the LIBSVM
  dataset collection.

modality: tabular

provenance:
  provider: LIBSVM
  upstream_name: cadata
  landing_page: https://example.org/
  retrieved_at: 2026-08-28

license:
  status: unknown

artifacts:
  - name: data
    format: libsvm
    compression: none
    size: 123456
    sha256: "..."
    distribution: upstream-only

    downloads:
      - kind: upstream
        url: https://...

representation:
  decoder: libsvm
  decoder_version: 1
  inputs:
    data: data
  options:
    index_base: 1
    feature_count: 8
    duplicate_features: error
    label_type: float64
    row_order: source
    target_name: response

tasks:
  - name: default
    type: regression
    target: response
```

An unsupervised dataset simply has no task:

```yaml
modality: tabular

artifacts:
  - name: data
    format: csv
    compression: none
    size: 12345
    sha256: "..."
    distribution: upstream-only

representation:
  decoder: delimited-text
  decoder_version: 1
  inputs:
    data: data
  options:
    encoding: utf-8
    delimiter: ","
    header: true
    quote: '"'
    escape: double
    missing_values: [""]
    columns:
      - {name: x, type: float64}
      - {name: group, type: string}
```

An image dataset may instead look roughly like:

```yaml
modality: image

artifacts:
  - name: images
    format: idx
    compression: none
    size: 12345
    sha256: "..."
    distribution: upstream-only
    downloads:
      - kind: upstream
        url: https://...

  - name: labels
    format: idx
    compression: none
    size: 123
    sha256: "..."
    distribution: upstream-only
    downloads:
      - kind: upstream
        url: https://...

representation:
  decoder: idx-images
  decoder_version: 1
  inputs:
    images: images
    labels: labels
  options: {}

tasks:
  - name: default
    type: classification
    target: labels
```

A text corpus might contain only a text artifact and no task.

Artifact names must be unique within a dataset version. Each representation
input refers to an artifact by name, making the required artifacts and their
assembly explicit.

Task targets refer to named elements of the decoded logical representation,
not directly to raw artifacts. A decoder contract must therefore define the
names and structure of its logical outputs.

Decoder contracts are part of the registry specification, not conventions
inferred from file extensions. Schema versions and decoder versions are
independent. A client must reject a manifest that uses a schema or decoder
version it does not understand rather than guessing how to interpret it.
Published decoder specification versions are immutable. A correction that can
change logical output requires a new decoder version and new versions of the
datasets whose representation recipes adopt it.

The precise schema should remain conservative initially. It should be
straightforward to add richer task and modality metadata later.

---

## Registry and artifact semantics

Every artifact must have a size and a SHA-256 digest computed over
the exact stored artifact bytes.

For HTTP retrieval, transfer framing is not part of the artifact. Clients must
disable transparent content decoding, request `identity` content encoding where
possible, and hash the response representation before applying the artifact's
declared compression or format decoder. Compression such as gzip or bzip2 must
therefore be declared explicitly in the manifest rather than inferred from a
URL or filename.

A URL is only a retrieval location. It is never the identity of an artifact.

Artifact retrieval follows this model:

```text
resolve dataset/version
        ↓
resolve required artifacts
        ↓
check local content-addressed cache
        ↓
download if absent
        ↓
verify SHA-256
        ↓
store atomically
        ↓
decode
```

Retrieval locations are tried in manifest order. On a transport error, size
mismatch, or hash mismatch, a client may discard the temporary file and try the
next location. Invalid bytes must never enter the cache. If no location
succeeds, the final error must preserve enough information to distinguish
unavailability from an integrity failure.

If an upstream provider changes a file in place, Datamonger must report an
integrity failure rather than silently accepting the new bytes. It may still
succeed from another location that serves the registered bytes, but the failed
location should be retained in diagnostic information.

Any change to the registered artifact bytes or representation semantics
requires a new dataset version, even if the change appears statistically or
semantically insignificant. Mirrors may be added or removed without a new
dataset version only when they serve bytes with the existing digest.

The cache should be conceptually content-addressed:

```text
cache/
└── objects/
    └── sha256/
        └── ...
```

The exact physical layout is private implementation detail, but cache keys and
their interpretation are shared semantics. A cache entry must not be accepted
merely because it appears at a hash-derived path; clients must verify its size
and digest before returning or decoding it. A later specification may permit a
carefully defined verification shortcut for very large artifacts.

Clients should use the standard application cache location for each operating system rather than assuming `~/.datamonger`.

Downloads must be written to temporary files, verified, and atomically
committed to the cache. Cache publication must be safe when several processes
request the same artifact concurrently. Interrupted, partial, or corrupt
downloads must never appear as valid cache entries.

Once artifacts are cached, normal retrieval should work offline.

---

## Mirrors, provenance, and licensing

Datamonger should not depend exclusively on upstream providers.

An artifact may have several retrieval locations:

```yaml
downloads:
  - kind: mirror
    url: ...

  - kind: upstream
    url: ...
```

The expected hash remains authoritative regardless of which location is used.

Datamonger-controlled mirrors should use durable object storage such as S3-compatible storage. Objects should preferably be stored by content hash so identical artifacts are naturally deduplicated.

Mirroring must be conservative.

Each artifact has a distribution policy:

```text
mirror
upstream-only
metadata-only
```

`mirror` means redistribution is understood to be permitted and
Datamonger-controlled storage may be listed.

`upstream-only` means Datamonger may retrieve and verify the artifact but should not host its own copy.

`metadata-only` means Datamonger can describe the artifact but cannot
automatically retrieve it. `fetch_artifact()` and any representation requiring
that artifact must fail before attempting network access. Metadata-only entries
are catalog records and do not satisfy Datamonger's retrieval guarantee.

Distribution policy belongs to the artifact because artifacts in the same
dataset may have different terms. License metadata may be shared at the dataset
level when it applies uniformly, or overridden per artifact.

Every dataset should record licensing information when known. Useful fields
include an SPDX expression when applicable, a license or terms URL, and the
evidence used to make the distribution decision. An unclear license must
prevent Datamonger-controlled mirroring. CI must reject a `mirror` artifact
unless its license metadata records a reviewed basis for redistribution.

CI must also enforce agreement between policy and locations: a `mirror`
artifact has at least one Datamonger-controlled location, an `upstream-only`
artifact has none, and a `metadata-only` artifact has no automatic download
locations.

Public availability must not be treated as permission to redistribute.

Kaggle should therefore not be part of the initial mirroring system. If supported later, it should normally use authenticated upstream retrieval with the user's own credentials.

Provenance should distinguish where data originated from where Datamonger currently retrieves it.

Useful provenance includes:

* provider;
* upstream dataset identifier;
* original name;
* landing page;
* authors;
* citation;
* upstream version;
* retrieval date.

---

## Client API

The primary operation is:

```text
fetch_data()
```

For example:

```r
fetch_data("cadata", source = "libsvm")
```

The operation means:

```text
resolve
→ retrieve
→ verify
→ decode
```

When `version` is omitted, resolution is relative to a specific registry
release. The client must make both the resolved canonical identifier and that
registry release available. Each client may use an idiomatic mechanism, such
as an optional `return_info` argument, but users must not need to inspect cache
paths or internal state to discover what was fetched.

The result should use a natural, documented representation in each language.

For example:

* tabular data may become an R data frame, pandas DataFrame, or Tables.jl-compatible table;
* matrix data may become dense or sparse native matrices;
* text may become an appropriate table or corpus representation;
* images may become arrays or an appropriate lightweight dataset object.

A format containing several logical components may produce an idiomatic record
or named tuple. For example, a LIBSVM representation can contain a sparse
feature matrix and a named response vector. This is faithful decoding of the
complete dataset, not task-specific `X, y` extraction.

Datamonger should not force all datasets into a common custom dataframe
abstraction. However, a decoder's return type in a given client must be stable
and must not change silently according to which optional packages happen to be
installed. If a decoder requires an optional dependency, the client should
raise a clear error with installation guidance; `fetch_artifact()` must remain
available without that decoding dependency.

Cross-language conformance applies to a canonical logical view of the decoded
result: values, missingness, names, shapes, ordering, and logical types. It does
not require identical host-language container types or bit widths.

Additional core operations should be small in number:

```text
fetch_data()
fetch_artifact()
data_info()
list_data()
```

`fetch_artifact()` retrieves a verified underlying artifact and returns its
local location without imposing a decoded representation. It accepts an
artifact name. The name may be omitted only when the dataset version contains
exactly one artifact; otherwise the client must report the available names.

`data_info()` exposes the resolved canonical identifier, registry release,
provenance, version, artifact names and hashes, licensing, modality,
representation, and task metadata. With an omitted dataset version, it reports
the version selected by the same resolution procedure as `fetch_data()`.

The clients should share a small semantic error taxonomy while mapping it to
idiomatic exception or condition types. It should distinguish at least:

* an unknown dataset or version;
* an unsupported registry schema or decoder;
* an unavailable metadata-only artifact;
* an unavailable artifact while offline;
* exhaustion of all retrieval locations;
* an artifact size or hash mismatch;
* a cache or decoding failure.

A simple `search_data()` may be added if useful, but sophisticated registry search is not an MVP requirement.

---

## Tasks and supervised learning

`fetch_data()` should not fundamentally mean “return `X` and `y`”.

For a tabular supervised dataset, returning the full table is often the most natural behavior.

Task metadata can then describe which column is conventionally used as the response.

For example:

```yaml
tasks:
  - name: default
    type: classification
    target: species
```

Datasets may eventually expose multiple tasks:

```yaml
tasks:
  - name: income
    type: regression
    target: income

  - name: occupation
    type: classification
    target: occupation
```

The initial implementation does not need sophisticated task APIs. It only needs a schema that does not make multiple or absent tasks impossible later.

A future helper could provide task-oriented extraction, for example:

```text
as_supervised(...)
```

but retrieval and statistical interpretation should remain conceptually separate.

---

## Formats and decoding

Datamonger should preserve original artifacts whenever practical.

The initial supported formats should be deliberately limited:

```text
CSV
TSV
LIBSVM / SVMLight
```

Compressed versions of these can be supported where straightforward.

Each supported format must have a versioned, language-neutral decoder
specification. For delimited text, the manifest must provide every dialect and
schema option needed for deterministic decoding. For LIBSVM/SVMLight, it must
provide the feature-index base, feature count or its derivation rule, duplicate
feature policy, label handling, and output ordering. Clients must not delegate
unspecified behavior to library defaults.

Archive files such as ZIP and tarballs may be artifacts themselves. Extraction
should happen only after hash verification and must reject absolute paths,
parent-directory traversal, unsafe links, duplicate output paths, and entries
that exceed defined file-count or expanded-size limits. These rules belong in
the shared decoder specification and conformance suite.

Datamonger should not silently perform statistical preprocessing such as:

* normalization;
* centering;
* imputation;
* one-hot encoding;
* feature selection.

Such operations belong downstream unless they are explicitly part of the registered definition of a particular dataset representation.

The MVP registry should therefore select UCI and OpenML entries whose exact
upstream or legally mirrorable artifacts can be decoded by the initial format
specifications. Repacking, cleaning, or converting unsupported source files is
not an implicit way around the MVP's format and transformation limits; a future
derived representation would need explicit provenance, its own artifacts and
recipe, and an identity distinct from the original representation.

---

## Registry distribution

The source registry consists of human-editable manifests.

CI should validate them against a machine-readable schema, preferably JSON Schema.

CI should reject at least:

* malformed identifiers;
* duplicate dataset versions;
* malformed hashes;
* missing required metadata;
* invalid artifact definitions;
* inconsistent registry entries.

CI must also compare the proposed registry with every relevant published
release and reject mutation of identity-bearing fields. Adding or changing a
default, mirror, citation, or license clarification is allowed only in a new
registry release. A dataset version is therefore append-only even though its
non-identity catalog metadata may evolve between registry releases.

A compact, deterministic registry index should be produced for clients so they
do not need to retrieve or scan thousands of individual YAML files. The index
must identify its schema version and registry release. Equivalent source trees
must generate byte-identical indexes.

The editable manifests remain canonical. Generated indexes must not be edited manually.

Registry releases should be immutable and versioned independently of R,
Python, and Julia package releases. A registry release fixes the complete
index, including default-version selections and catalog metadata.

Initially, clients may ship with a registry snapshot. The three clients should
ship the same registry release when making a coordinated release. More
sophisticated registry updating can be introduced later, but updates must be
explicit and must select an immutable registry release rather than silently
tracking a branch.

A mutable branch such as `main` should not become an implicit source of reproducibility-sensitive state.

Until registry signing is implemented, the trust root is the registry snapshot
delivered through the client package or another explicitly configured trusted
channel. SHA-256 detects corruption or substitution relative to that snapshot;
it does not authenticate a maliciously replaced snapshot. Documentation and
security claims must preserve this distinction.

---

## Cross-language behavior

R, Python, and Julia should implement the same registry semantics but remain idiomatic within their ecosystems.

Cross-language consistency is defined relative to the same registry release
and supported specification versions. Explicit dataset identifiers must resolve
identically in every registry release that contains them. Defaults may differ
between registry releases, which is why unversioned calls must report both the
resolved identifier and registry release.

The clients should share conformance fixtures that verify, at minimum, that they:

* resolve the same dataset/version;
* report the same registry release and canonical identifier;
* resolve the same artifact hashes;
* hash the same stored bytes despite HTTP transfer behavior;
* follow the same retrieval-location fallback rules;
* detect corrupt downloads;
* publish safely when concurrent processes request the same artifact;
* use cached artifacts offline;
* interpret registry metadata consistently;
* reject unsupported schema and decoder versions;
* decode the same logical values, missingness, names, shapes, ordering, and
  logical types;
* classify failures according to the shared error taxonomy.

Tiny local fixtures and a local HTTP test server should be used for basic CI
rather than depending on large external datasets. Golden decoded results
should use a language-neutral serialization so each client is tested against
the specification, not against another client's output.

The packages should remain relatively lightweight. Heavy dataframe or machine-learning dependencies should be optional wherever possible.

---

## MVP

The first useful version should focus on proving that the registry model works.

Support three sources:

```text
LIBSVM
UCI
OpenML
```

Register roughly 20–30 datasets covering:

* regression;
* binary classification;
* multiclass classification;
* unsupervised data;
* dense data;
* sparse data;
* multiple artifacts where useful.

Support only a few formats initially:

```text
CSV
TSV
LIBSVM / SVMLight
```

Implement in all three clients:

```text
fetch_data()
fetch_artifact()
data_info()
list_data()
```

Implement:

* a normative registry, identity, retrieval, and decoder specification;
* immutable, independently versioned registry releases;
* registry resolution;
* local caching;
* SHA-256 verification;
* atomic downloads;
* concurrency-safe cache publication;
* deterministic retrieval-location fallback;
* offline reuse;
* basic decoding with explicit representation recipes;
* stable per-client return types;
* the shared error taxonomy and conformance suite.

Do not initially implement:

* user uploads;
* accounts;
* a web application;
* arbitrary private datasets;
* data transformations;
* model storage;
* benchmarking;
* sophisticated search;
* registry signing;
* lockfiles;
* huge-data streaming;
* Kaggle mirroring.

The first goal is not breadth. It is demonstrating that the same dataset can be retrieved reproducibly from R, Python, and Julia using a stable shared registry.

The MVP is intentionally substantial, but it should be delivered as vertical,
test-driven milestones:

1. Define the registry schema, identity rules, decoder contracts, deterministic
   index generator, immutable test registry release, and golden fixtures.
2. Implement registry resolution and `fetch_artifact()` in all three clients,
   including hashing, fallback, concurrent caching, corruption, and offline
   conformance tests.
3. Implement one representation decoder in all three clients and prove logical
   output conformance end to end.
4. Implement the remaining initial decoders and multi-artifact assembly.
5. Populate and review the 20–30 real dataset manifests across the three
   sources, then run end-to-end retrieval tests separately from hermetic CI.

Every milestone should leave all three clients conforming to the same registry
and specification revision. This sequencing manages implementation risk
without reducing the MVP's promised scope.

---

## Longer-term direction

Potential later additions include:

* project lockfiles;
* signed registry releases;
* richer task definitions;
* additional modalities;
* authenticated upstream providers;
* archival mirrors;
* registry tooling for adding datasets;
* command-line tools;
* additional language clients.

These should be driven by actual use rather than designed up front.

Datamonger's value ultimately rests on a simple promise:

> A researcher should be able to identify a dataset today and retrieve the same registered data years later, without caring where the original provider happens to host it.

Dataset acquisition should become boring, stable infrastructure.
