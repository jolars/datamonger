# Datamonger Design

This document records architecture and rationale. Normative draft contracts and
wire requirements live in `spec/`; where wording differs, the versioned
specification controls.

## Overview

Datamonger is a cross-language system for retrieving, caching, verifying, and
decoding public research datasets reproducibly.

It provides clients for R, Python, and Julia backed by a shared registry.

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

The important property is that a registered dataset version refers to stable,
verifiable bytes and a stable, verifiable interpretation. Provider URLs may
move or begin serving different bytes without changing that identity. Continued
retrievability after every provider and cache disappears is a stronger
preservation guarantee, and Datamonger claims it only for artifacts with a
durable preservation copy.

Datamonger is therefore best thought of as a **dataset registry and artifact
system with language-specific clients**, rather than as a downloading library.

---

## What problem this actually solves

Downloading a file, checking a hash, and caching it is solved in every target
language already. Python has `pooch` and the `scikit-learn` fetchers, Julia has
`DataDeps.jl` and `MLDatasets.jl`, and R has `pins` and `piggyback`. OpenML has
mature clients in all three. Data Retriever provides a curated cross-language
catalog, though it cleans and transforms data, which Datamonger deliberately
does not.

What none of these provide is the property Datamonger exists for:

> The same registered dataset yields the same bytes **and the same logical
> values** in R, Python, and Julia whenever its registered artifacts remain
> available.

Byte-level integrity is the easy half and is widely available. The hard half is
decoding agreement. Three languages reading the same CSV with their default
readers will disagree about type inference, missing-value tokens, quoting edge
cases, and column naming. Two versions of the same language, years apart, may
also disagree. A benchmark comparing an algorithm's R, Python, and Julia
implementations is only meaningful if the inputs are identical, and today
nothing guarantees that.

This narrows the audience but sharpens the pitch. The primary user is a
methods researcher who needs identical inputs across language ecosystems, or
who needs to rerun an experiment years after publication. Everything else is a
consequence.

It also narrows the source list. LIBSVM and UCI mutate files in place, reshuffle
URLs, and have no version concept at all, so pinning them is worth a great deal.
OpenML already offers immutable versioned datasets with checksums, stable IDs,
hosting, and good clients, so wrapping it adds surface area without adding much.
OpenML is therefore deferred to a later provider adapter.

---

## Goals and non-goals

Datamonger should make public research datasets:

* consistently identifiable and identically decoded across R, Python, and Julia;
* verifiable at both the byte level and the decoded-value level;
* independent of fragile upstream URLs for identity and verification;
* reproducible across time and machines;
* locally cacheable and usable offline after retrieval;
* explicit about provenance and licensing;
* easy to retrieve.

Datamonger is not intended to become another Kaggle, OpenML, or Hugging Face
Hub. It should not require user accounts, provide arbitrary uploads, host
models, perform remote computation, or become a general-purpose data publishing
platform.

The central design principle is:

> A published dataset version identifies immutable artifacts and an immutable
> interpretation of them.

URLs, mirrors, storage providers, and client implementations may change. The
underlying artifact identity and decoded meaning must not.

Here, "verified" means that retrieved bytes and their interpretation match a
trusted registry release. SHA-256 provides integrity relative to that registry.
Authenticating the registry itself is a separate concern, addressed under
[Registry distribution](#registry-distribution).

### Four separate guarantees

The project distinguishes four properties that are easy to conflate:

* **Identity** fixes the artifact bytes and representation recipe denoted by a
  dataset version.
* **Integrity** detects whether retrieved bytes and decoded logical values match
  that identity.
* **Availability** means that a verified retrieval location or local cache
  currently supplies the registered bytes.
* **Preservation** means that a durable, independently administered copy is
  expected to remain available if the upstream provider disappears.

Every registered, automatically retrievable dataset provides identity and
integrity. An `upstream-only` artifact provides availability only while an
upstream location or local cache works. Only an artifact with distribution
policy `mirror` and a reviewed durable preservation location provides the
preservation guarantee. User-facing metadata and documentation must report
these properties separately rather than implying that a digest creates a
copy of the data.

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
├── spec/                     # normative specification
│   ├── identity.md
│   ├── retrieval.md
│   ├── canonical-form.md
│   ├── index.md
│   ├── decoders/
│   │   ├── delimited-text-v1.md
│   │   └── libsvm-v1.md
│   └── schema/               # JSON Schema for manifests and the index
│
├── registry/
│   ├── datasets/
│   │   ├── libsvm/
│   │   └── uci/
│   └── releases/             # generated, immutable indexes
│
├── packages/
│   ├── r/
│   ├── python/
│   └── julia/
│
├── tools/
│   ├── dm-add                # manifest authoring
│   ├── dm-index              # deterministic index generation
│   └── dm-canary             # upstream drift checking
│
└── tests/
    ├── fixtures/             # tiny local artifacts
    ├── golden/               # canonical decoded forms
    └── conformance/
```

The specification lives at the top level rather than inside `registry/` because
it governs clients, tooling, and registry content alike. It is the shared core
of the system.

---

## Implementation strategy

### One reference client first

The clients should not be developed in lockstep from the start. Building three
implementations against a specification that is still changing triples the cost
of every specification change, during exactly the period when changes are most
frequent.

The sequence is therefore:

1. Draft only enough specification for the vertical proof.
2. Build one reference client end to end, and let real use break and harden the
   specification.
3. Cut a feature-frozen specification release candidate.
4. Port to the remaining two clients, driven by the conformance suite. Any
   ambiguity or conformance failure produces a corrected release candidate.
5. Freeze specification revision 1 and publish stable verification records only
   after independent implementations agree.

R is the recommended reference client. Its packaging environment has the
tightest constraints, in particular CRAN's policy that a package must not write
outside the session temporary directory without explicit user consent, and its
dependency culture is the most conservative. Discovering those constraints
first is cheaper than discovering them last. The choice is not load-bearing,
though, and using whichever client will see daily use is a defensible
alternative.

Losing the "three languages on day one" story for a few months is worth a
specification that has survived contact with reality before being paid for
three times.

### Independent implementations, for now

There is no shared native implementation initially. Cross-language consistency
is defined by the specification and the conformance suite, not by shared
implementation code.

This decision deserves periodic re-examination rather than being treated as
settled. A Rust core exposed through extendr, PyO3, and a Julia binding would
collapse the conformance problem precisely where it is hardest, which is
decoding. The fetch, hash, and cache layer is easy to write three times.
LIBSVM and delimited-text edge cases are not, and they are where silent
divergence actually occurs.

The arguments for staying independent are packaging weight, simpler
contribution for language specialists, CRAN and Julia binary distribution
friction, and the fact that pure-language clients install anywhere. The
arguments against are the recurring cost of triplicated decoder work and the
permanent risk of drift.

The concrete decision rule: if the conformance suite repeatedly catches decoder
divergence that is expensive to fix in three places, migrate decoding to a
shared native core while keeping registry resolution, caching, and result
construction idiomatic per language.

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
lockfiles, logs, URLs, and debugging:

```text
libsvm:cadata@1
```

The specification defines this syntax normatively so all clients serialize it
identically. Initially, `source` and `name` use lowercase ASCII identifiers
matching `[a-z0-9][a-z0-9._-]*`. A version is an opaque ASCII string matching
`[A-Za-z0-9][A-Za-z0-9._+-]*`. Versions are case sensitive, and clients must
not infer version ordering from their spelling.

`source` is a stable registry namespace describing the provenance collection,
not the URL or mirror used to retrieve an artifact.

If `version` is omitted, the default version in the selected registry release
is used. This is a convenience query, not a reproducible identifier. Clients
must make the resolved canonical dataset identifier and registry release
visible through returned metadata, an optional `return_info`-style result, or
an equally explicit idiomatic mechanism.

A specific published version must never change meaning.

Here, "meaning" denotes the artifact identity and logical result of the
representation. It does not mean that the complete catalog record is frozen:
release-scoped descriptions, locations, task availability, verification
attestations, and errata may differ as allowed below. Reproducing the complete
record therefore requires the registry release as well as the dataset
identifier.

### Identity-bearing fields

The identity-bearing fields of a dataset version are:

* its source, name, and version;
* the names, sizes, digests, formats, and compression of its artifacts;
* its representation recipe, meaning decoder name, decoder specification
  version, inputs, and every option.

Changing any identity-bearing field requires a new dataset version.

The following are **not** identity-bearing and may be updated by a later
registry release without a new dataset version:

* retrieval locations, provided they serve the registered bytes;
* descriptive metadata such as titles, descriptions, citations, and license
  clarifications;
* cross-source relations;
* task definitions, subject to the append-only rule below.

`modality` and the expected decoded shape are **derived** from the
representation rather than independently declared. They are recorded in the
manifest for searchability and verification, and CI must check that they agree
with the representation rather than trusting them.

CI must compare new registry releases with every relevant published release and
reject changes to identity-bearing fields. Validating only the current tree is
insufficient.

---

## Data model

Datamonger distinguishes four concepts.

### Artifact

An artifact is an immutable sequence of bytes identified by a cryptographic
digest.

Examples:

* a CSV file;
* a compressed LIBSVM file;
* a ZIP archive;
* a collection of image files stored in an archive.

Artifacts are the foundation of byte-level reproducibility.

### Representation

A representation is a deterministic recipe for decoding one or more artifacts
into logical data. It identifies its input artifacts, a versioned decoder
contract, and every option that can affect the result.

For example, a delimited-text representation specifies the character encoding,
delimiter, quoting and escaping rules, header handling, missing-value tokens,
and logical column types. A LIBSVM representation specifies the feature-index
base, feature count, label handling, duplicate-feature policy, and ordering
rules.

The representation contract concerns logical values, names, shapes, and
ordering, formalized by the [canonical logical
form](#the-canonical-logical-form). Clients may use different native
containers, integer widths, or sparse-matrix implementations as long as the
canonical logical form agrees.

### Dataset

A dataset is the meaningful data obtained by applying a representation recipe
to one or more artifacts.

A dataset may be tabular, a dense or sparse matrix, image data, text, a time
series, graph data, audio, or another modality. A dataset does not inherently
need to have a response variable.

### Task

A task is an optional interpretation of a dataset for a statistical or
machine-learning problem, such as classification, regression, or multilabel
classification. A task may specify a target, features, predefined splits, or
related information.

Tasks are metadata layered on top of datasets. They are not part of the
fundamental definition of what a dataset is, and they are correspondingly not
identity-bearing.

Reproducibility is preserved by an **append-only, individually immutable**
rule:

* a published task definition may never be changed or removed;
* a new task may be added to an existing dataset version in a later registry
  release;
* CI enforces both.

The pair `(dataset version, task name)` therefore never changes meaning, which
is the property users actually need, without forcing dataset version churn for
reasons unrelated to the data. Clients report the registry release alongside
task metadata so that "which tasks exist" remains answerable and pinnable.

This distinction allows the same system to represent supervised, unsupervised,
image, text, and other forms of data without forcing everything into an `X, y`
abstraction.

---

## The canonical logical form

Cross-language decoding agreement is only enforceable if "the same logical
values" has a byte-exact definition. The specification defines a canonical
logical form: a deterministic serialization of a decoded result, used for
golden fixtures, for conformance testing, and for the per-dataset decoded
digests described below.

The canonical form is deliberately small and bespoke rather than reusing Arrow
IPC. Arrow would add a heavy dependency to all three clients and introduces its
own canonicalization questions around dictionary encoding, buffer padding, and
schema metadata. A purpose-built format keeps runtime dependencies small, but
it is a protocol rather than a serialization helper. It requires a complete
normative byte-level specification, exhaustive test vectors, malformed-input
tests, property tests, and cross-language fuzz cases.

The form serializes a decoded result as an ordered sequence of named logical
components. Rules:

* **Framing.** A magic header, the canonical-form version, then each component
  as name, kind, logical element type, rank, dimensions, validity, and values.
  The specification fixes every tag, integer width, byte order, and
  length-prefix encoding.
* **Components and names.** Component order is fixed by the decoder contract;
  clients never sort native container output. Names are unique UTF-8 byte
  strings, length-prefixed, with no Unicode normalization.
* **Missingness.** An explicit validity bitmap per component. Sentinel values
  are never used to express missingness. The specification fixes bitmap bit
  order and requires unused bits and value storage for invalid elements to have
  canonical zero representations.
* **Floats.** Raw IEEE 754 binary64 bit patterns, little-endian. Negative zero
  is normalized to positive zero and all NaNs are normalized to the canonical
  quiet NaN `0x7ff8000000000000`. Hashing bit patterns rather than formatted
  decimals removes every float-formatting difference between languages.
* **Integers.** Two's complement, little-endian, fixed width for the declared
  logical type.
* **Strings.** Logical strings are UTF-8 bytes, length-prefixed, with no Unicode
  normalization. A decoder performs the manifest-declared character decoding;
  invalid input for that encoding is a decoding error.
* **Booleans.** One bit per element in a packed bitmap whose bit order and
  padding are fixed by the specification.
* **Dense matrices.** Explicit dimensions and row-major logical value order,
  independent of the host language's physical matrix layout.
* **Sparse matrices.** An explicit logical element type and dimensions, with
  entries in row-major order and ascending column index within each row. Index
  widths and bases are fixed by the canonical-form version. Duplicate entries,
  stored zeros, and missing sparse values are rejected in version 1.
* **Row ordering.** Determined by the representation's `row_order` option, most
  commonly `source`.

The canonical form defines the serialization of values after decoding. Each
decoder specification must separately define the accepted lexical grammar and
conversion rules that produce those values, including decimal-to-binary64
rounding, overflow, non-finite values, whitespace, byte-order marks, invalid
text, and missing-value matching. Canonicalizing a float after parsing does not
make underspecified parsers agree.

The initial logical type set is deliberately minimal:

```text
float64
int64
string
bool
```

Categorical, temporal, and decimal types are deferred. A categorical column is
represented as `string` until a specification revision defines something
better. This is a real scope reduction and it removes the largest remaining
source of cross-language type-inference disagreement.

Clients compute its hash incrementally while decoding; they need not materialize
a second complete copy of the result. Decoded verification is enabled by
default. A caller may explicitly disable it, but returned metadata must then
record that only artifact integrity was verified.

### Canonical-form lifecycle

The representation defines logical meaning, while the canonical form is a
versioned verification encoding of that meaning. Changing canonical framing
alone does not require a new dataset version.

The `expect.verification` list pins the canonical-form version and digest
algorithm for every recorded digest. A later registry release may append a
digest for a newer canonical-form version while retaining earlier records.
Clients use a supported, non-revoked record and report which one they used.
Once every currently supported registry release supplies a newer record, a
client may retire the older canonical-form implementation. A client opening an
older pinned release may therefore require an older client, just as it may for
a retired decoder version.

Verification records are append-only. A wrong digest is never overwritten. A
later immutable registry release may contain a maintainer-approved erratum that
revokes the bad record and appends a replacement. This corrects verification
metadata, not dataset meaning; earlier registry releases remain unchanged and
continue to expose the error.

---

## Registry manifests

Each dataset version is represented by a human-readable manifest, authored in
YAML.

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

related:
  - id: uci:california-housing@1
    relation: same_upstream

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
  expect:
    components:
      - {name: features, kind: sparse_matrix, rows: 20640, columns: 8}
      - {name: response, kind: vector, type: float64, length: 20640}
    verification:
      - {canonical_form: 1, algorithm: sha256, digest: "..."}

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
    downloads:
      - kind: upstream
        url: https://...

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
    row_order: source
    columns:
      - {name: x, type: float64}
      - {name: group, type: string}
  expect:
    components:
      - {name: x, kind: vector, type: float64, length: 500}
      - {name: group, kind: vector, type: string, length: 500}
    verification:
      - {canonical_form: 1, algorithm: sha256, digest: "..."}
```

Every example must carry the fields CI requires, including `downloads`, since
examples in this document are read as normative by implementers.

### Multiple artifacts and predefined splits

LIBSVM routinely ships a separate test file, so multi-artifact assembly and
predefined splits appear immediately rather than eventually. A decoder contract
defines the names and structure of its logical outputs, which makes this
expressible without special-casing:

```yaml
artifacts:
  - name: train
    format: libsvm
    compression: bzip2
    size: 1234567
    sha256: "..."
    distribution: upstream-only
    downloads:
      - kind: upstream
        url: https://...

  - name: test
    format: libsvm
    compression: bzip2
    size: 234567
    sha256: "..."
    distribution: upstream-only
    downloads:
      - kind: upstream
        url: https://...

representation:
  decoder: libsvm-split
  decoder_version: 1
  inputs:
    train: train
    test: test
  options:
    index_base: 1
    feature_count: 123
    duplicate_features: error
    label_type: int64
    row_order: source
    target_name: response
  expect:
    components:
      - {name: train_features, kind: sparse_matrix, rows: 32561, columns: 123}
      - {name: train_response, kind: vector, type: int64, length: 32561}
      - {name: test_features,  kind: sparse_matrix, rows: 16281, columns: 123}
      - {name: test_response,  kind: vector, type: int64, length: 16281}
    verification:
      - {canonical_form: 1, algorithm: sha256, digest: "..."}

tasks:
  - name: default
    type: classification
    splits:
      train:
        features: train_features
        target: train_response
      test:
        features: test_features
        target: test_response
```

`fetch_data()` returns all four components in an idiomatic record. It does not
silently concatenate the splits, and it does not silently discard the test set.
Each named task split maps every role needed by that split, rather than treating
the target as a single dataset-wide field. Row-partition splits for a single
table use the same principle: the task contract identifies the table and an
immutable partition assignment for each split.

### The `expect` block

`expect` is the most important addition to the manifest schema. It records what
the representation must produce:

* the names, kinds, logical types, and shapes of the decoded components;
* one or more versioned verification records containing a canonical-form
  version, digest algorithm, and digest of the decoded result.

This changes the guarantee from "we verified the bytes" to "we verified the
meaning." Without it, cross-client decoding agreement is only tested against
tiny local fixtures, and three clients can quietly diverge on a real dataset
with nothing to catch it. With it, any client can verify its decoding of any
registered dataset against the registry rather than against another client, and
decoder bugs become loud instead of silent.

The shape fields also make `list_data()` and any future search genuinely
useful, since row and column counts are the first thing anyone filters on.

`expect` is derived from the artifacts and the representation, so it is not
independently identity-bearing. Component expectations and published
verification records are nevertheless immutable. New verification records may
be appended under the canonical-form lifecycle above. Correcting a wrongly
recorded component expectation or digest requires an explicit erratum record
with maintainer sign-off, so that a decoder change can never be laundered as a
metadata fix. A client encountering a non-revoked digest mismatch must report
it as an integrity failure, distinct from a decoding failure.

`dm-add` computes a candidate digest at manifest authoring time. A stable
registry release may publish it only after a second, independent implementation
has reproduced it. Before that, the manifest may appear in a clearly marked
prerelease registry for reference-client development, but it does not carry the
cross-language verification claim. Human review must also inspect decoded
shapes, names, and representative values; two implementations can reproduce the
same mistaken manifest recipe.

Hermetic CI checks schema, format, internal consistency, and the independent
implementations against local golden fixtures. The [canary](#operations)
re-verifies real artifacts on a schedule with each released implementation,
rather than only rerunning the implementation that authored the digest.

### General manifest rules

Artifact names must be unique within a dataset version. Each representation
input refers to an artifact by name, making the required artifacts and their
assembly explicit.

Task targets refer to named elements of the decoded logical representation, not
directly to raw artifacts.

Decoder contracts are part of the specification, not conventions inferred from
file extensions. Schema versions and decoder versions are independent. A client
must reject a manifest that uses a schema or decoder version it does not
understand rather than guessing how to interpret it.

`size` is not a second integrity check, since SHA-256 already covers that. It
exists for early abort on obviously wrong responses, for preallocation, and for
progress reporting.

The `related` field records that the same underlying data appears in several
source collections under different preprocessing. Nothing consumes it
initially, but users will immediately ask which of several near-identical
entries to use, and recording the relation at authoring time is far cheaper
than reconstructing it later.

The precise schema should remain conservative initially. It should be
straightforward to add richer task and modality metadata later.

---

## Registry and artifact semantics

Every artifact must have a size and a SHA-256 digest computed over the exact
stored artifact bytes.

### HTTP retrieval and what exactly gets hashed

This needs to be precise, because `curl`, `httr2`, `requests`, and `HTTP.jl`
have different defaults for transparent decompression, and this is exactly the
kind of detail that produces silent cross-language divergence.

In RFC 9110 terms, a representation includes its content codings. The artifact
is defined as **the content after all HTTP content-codings have been removed,
and before the artifact's own declared compression is touched.**

The normative rule is therefore:

1. Request `Accept-Encoding: identity`.
2. Undo exactly the content-codings the server declares in `Content-Encoding`,
   and no others.
3. Hash the result.
4. Only then apply the artifact's declared `compression` and format decoder.

Transfer framing, such as chunked transfer encoding, is never part of the
artifact.

File-level compression must be declared explicitly in the manifest and must
never be inferred from a URL or filename.

There is a known hazard worth documenting rather than discovering later: some
servers serve a `.gz` file with `Content-Encoding: gzip`, which means the same
artifact hashes differently depending on which mirror answers. The policy is
that such a location is misconfigured and must not be registered as a retrieval
location for a compressed artifact. `dm-add` detects the condition at authoring
time and refuses, and the canary reports it if a location develops the behavior
later.

### Retrieval

A URL is only a retrieval location. It is never the identity of an artifact.

```text
resolve dataset/version
        ↓
resolve required artifacts
        ↓
check local content-addressed cache
        ↓
download if absent
        ↓
verify size and SHA-256
        ↓
store atomically
        ↓
decode
        ↓
compute canonical-form digest incrementally
        ↓
verify decoded values (default)
```

A caller may explicitly skip decoded verification when performance or
diagnostic work requires it. Artifact verification is never skipped, and result
metadata distinguishes artifact-only verification from full decoded
verification.

Retrieval locations are tried in manifest order. On a transport error, size
mismatch, or hash mismatch, a client may discard the temporary file and try the
next location. Invalid bytes must never enter the cache. If no location
succeeds, the final error must preserve enough information to distinguish
unavailability from an integrity failure.

If an upstream provider changes a file in place, Datamonger must report an
integrity failure rather than silently accepting the new bytes. It may still
succeed from another location that serves the registered bytes, and the failed
location must be retained in diagnostic information.

Any change to the registered artifact bytes or representation semantics
requires a new dataset version, even if the change appears statistically or
semantically insignificant. Retrieval locations may be added or removed without
a new dataset version only when they serve bytes with the registered digest.

### Cache

The cache is conceptually content-addressed:

```text
cache/
└── objects/
    └── sha256/
        └── ...
```

Cache keys and their interpretation are shared semantics, but the MVP uses a
separate cache root and private physical layout for each language client. A
client must not inspect or mutate another client's cache. A future shared
cross-language cache would require a normative layout, lock protocol, crash
recovery rules, and compatibility version; merely pointing three
implementations at the same directory is unsafe.

A cache entry must not be accepted merely because it appears at a hash-derived
path. Clients must verify its size and digest before returning or decoding it. A
later specification revision may permit a carefully defined verification
shortcut for very large artifacts.

Downloads must be written to temporary files, verified, and atomically
committed. Cache publication must be safe when several processes request the
same artifact concurrently. Interrupted, partial, or corrupt downloads must
never appear as valid cache entries. Each client specifies a portable
publication, reader-lease, and eviction-lock protocol, including stale-lock and
crash recovery behavior.

Once artifacts are cached, normal retrieval works offline.

Clients use the standard application cache location for each operating system
rather than assuming `~/.datamonger`. In R this means `tools::R_user_dir()`,
and CRAN policy requires explicit user consent before first writing there. The
R client must therefore prompt on first use in an interactive session, honor a
configuration option in a non-interactive one, and fall back to the session
temporary directory when consent is absent. Julia's `DataDeps.jl` has
established a comparable consent norm, and the Julia client should follow it.
Datamonger performs no telemetry of any kind, and this should be stated in each
package's documentation.

The cache needs management operations from the start, because unbounded growth
is a real problem and eviction interacts with the offline guarantee:

```text
cache_info()
cache_clean()
```

`cache_info()` reports location, total size, and per-artifact entries with the
dataset versions that reference them. `cache_clean()` removes entries by
dataset, by age, or entirely, and must never remove an entry while another
process is publishing or reading it. A cleaner acquires the exclusive side of
the same per-object lease and skips active objects rather than blocking or
invalidating a decode. Eviction is manual. Datamonger never evicts
automatically, since doing so would break offline reuse without warning.

---

## Mirrors, provenance, and licensing

### Mirroring is deferred, and when it arrives it targets Zenodo

Datamonger-controlled mirroring is **not** part of the MVP.

Upstream-only retrieval plus verification already delivers the core value:
detecting when upstream data changes and refusing to hand back the wrong bytes.
Mirroring, by contrast, is where the per-artifact legal review cost and the
liability live, and it is the part most likely to stall the project before it
has any users. Ship verification first, then mirror the datasets that actually
demonstrate rot.

When mirroring does arrive, the default host is Zenodo, not S3-compatible
object storage. S3 costs money every month indefinitely, and it disappears when
the grant, the payment method, or the maintainer's interest does, which defeats
the entire purpose of the system. Zenodo is free, permanent, DOI-addressed, run
by CERN, accepts large deposits, and carries an institutional framing that
makes redistribution of research datasets normal rather than novel. A DOI is
also a far better thing to cite in a paper than a bucket URL.

Object storage such as R2 or S3 may later be added purely as a bandwidth cache
in front of Zenodo, storing objects by content hash so identical artifacts
deduplicate naturally. It should never be the only copy.

### Distribution policy

The manifest schema carries distribution policy from the start, even though
mirroring is deferred, so that the field does not have to be retrofitted:

```text
mirror
upstream-only
metadata-only
```

`mirror` means redistribution is understood to be permitted and
Datamonger-controlled storage may be listed. No MVP artifact uses it.

Distribution permission is not preservation. A mirrored artifact records a
separate preservation status. `durable` requires a reviewed, immutable
institutional deposit intended for long-term retention; an object-store cache
or project web server remains `none`. The preservation record identifies the
deposit, review evidence, and review date. Thus a `mirror` artifact may improve
availability without carrying the preservation guarantee. An absent
preservation record is equivalent to `none`.

`upstream-only` means Datamonger may retrieve and verify the artifact but does
not host its own copy.

`metadata-only` means Datamonger can describe the artifact but cannot
automatically retrieve it. `fetch_artifact()` and any representation requiring
that artifact must fail before attempting network access. Metadata-only entries
are catalog records and do not satisfy Datamonger's retrieval guarantee.

Distribution policy belongs to the artifact, because artifacts in the same
dataset may have different terms. License metadata may be shared at the dataset
level when it applies uniformly, or overridden per artifact.

Every dataset should record licensing information when known: an SPDX
expression when applicable, a license or terms URL, and the evidence used to
make the distribution decision. An unclear license must prevent
Datamonger-controlled mirroring. CI must reject a `mirror` artifact unless its
license metadata records a reviewed basis for redistribution, and must enforce
agreement between policy and locations, so that a `mirror` artifact has at
least one Datamonger-controlled location, an `upstream-only` artifact has none,
and a `metadata-only` artifact has no automatic download locations. CI also
rejects `preservation: durable` unless the artifact is distributable, the
deposit serves the registered digest, and the preservation review fields are
complete.

Public availability must not be treated as permission to redistribute.

Kaggle is not part of the mirroring system. If supported later, it should use
authenticated upstream retrieval with the user's own credentials.

### Provenance

Provenance distinguishes where data originated from where Datamonger currently
retrieves it. Useful provenance includes the provider, upstream dataset
identifier, original name, landing page, authors, citation, upstream version,
and retrieval date.

---

## Client API

The primary operation is:

```text
fetch_data()
```

It means:

```text
resolve → retrieve → verify artifact → decode → verify logical values
```

When `version` is omitted, resolution is relative to a specific registry
release. The client must make both the resolved canonical identifier and that
registry release available. Each client may use an idiomatic mechanism, such as
an optional `return_info` argument, but users must not need to inspect cache
paths or internal state to discover what was fetched.

Decoded verification is on by default. Each client exposes an idiomatic
`verify_decoded = true`-style option and reports the canonical-form version and
digest used. Disabling it is explicit and is reflected in returned metadata;
it does not disable artifact size and SHA-256 verification.

The result uses a natural, documented representation in each language:

* tabular data becomes an R data frame, a pandas DataFrame, or a
  Tables.jl-compatible table;
* matrix data becomes dense or sparse native matrices;
* text becomes an appropriate table or corpus representation;
* multi-component results become an idiomatic record or named tuple.

A LIBSVM representation, for example, contains a sparse feature matrix and a
named response vector. That is faithful decoding of the complete dataset, not
task-specific `X, y` extraction.

Datamonger does not force all datasets into a common custom dataframe
abstraction. However, a decoder's return type in a given client must be stable
and must not change silently according to which optional packages happen to be
installed. If a decoder requires an optional dependency, the client raises a
clear error with installation guidance, and `fetch_artifact()` remains
available without that decoding dependency.

Cross-language conformance applies to the canonical logical form, not to host
container types or bit widths.

### Core operations

```text
fetch_data()
fetch_artifact()
data_info()
list_data()
cache_info()
cache_clean()
```

`fetch_artifact()` retrieves a verified underlying artifact and returns its
local location without imposing a decoded representation. It accepts an
artifact name. The name may be omitted only when the dataset version contains
exactly one artifact; otherwise the client must report the available names.

`data_info()` exposes the resolved canonical identifier, registry release,
provenance, artifact names and hashes, distribution and preservation status,
licensing, modality, representation, expected shapes, verification records,
related datasets, and task metadata. The structured information returned with
`fetch_data()` additionally reports whether decoded verification ran and which
record it used. With an omitted dataset version, `data_info()` reports the
version selected by the same resolution procedure as `fetch_data()`.

`list_data()` enumerates the datasets in the active registry release, with
enough shape and modality metadata to filter usefully.

A simple `search_data()` may be added if useful. Sophisticated registry search
is not an MVP requirement.

### Naming

`fetch_data` is a generic name, and in R in particular it is a plausible
collision with user code and other packages. Before the first release, decide
whether to keep it, prefix it, or export both a prefixed canonical name and an
unprefixed alias. This is cheap now and expensive once it is in anyone's
scripts.

### Error taxonomy

The clients share a small semantic error taxonomy, mapped to idiomatic
exception or condition types. The normative categories and precedence are
defined in [the error specification](spec/errors.md). They distinguish at
least:

* an unknown dataset or version;
* an unsupported registry schema or decoder version;
* an unavailable metadata-only artifact;
* an unavailable artifact while offline;
* exhaustion of all retrieval locations;
* an artifact size or hash mismatch;
* a decoded-value mismatch against `expect`;
* a cache failure;
* a decoding failure.

An artifact hash mismatch, a decoded-value mismatch, and a decoding failure are
three different things, and conflating them makes upstream drift impossible to
diagnose.

---

## Tasks and supervised learning

`fetch_data()` does not fundamentally mean "return `X` and `y`".

For a tabular supervised dataset, returning the full table is usually the most
natural behavior. Task metadata then describes which column is conventionally
used as the response:

```yaml
tasks:
  - name: default
    type: classification
    target: species
```

Datasets may expose multiple tasks:

```yaml
tasks:
  - name: income
    type: regression
    target: income

  - name: occupation
    type: classification
    target: occupation
```

The initial implementation does not need sophisticated task APIs. It needs a
schema that does not make multiple or absent tasks impossible later, plus the
append-only immutability rule described under [Task](#task).

A future helper could provide task-oriented extraction, for example
`as_supervised(...)`, but retrieval and statistical interpretation should
remain conceptually separate.

---

## Formats and decoding

Datamonger preserves original artifacts whenever practical.

The initial supported formats are deliberately limited:

```text
CSV
TSV
LIBSVM / SVMLight
```

Compressed versions of these are supported where straightforward, with
compression declared explicitly in the manifest.

Each supported format has a versioned, language-neutral decoder specification.
For delimited text, the manifest must provide every dialect and schema option
needed for deterministic decoding. For LIBSVM and SVMLight, it must provide the
feature-index base, feature count or its derivation rule, duplicate-feature
policy, label handling, and output ordering. Clients must not delegate
unspecified behavior to library defaults.

The delimited-text option vocabulary should follow Frictionless Data's CSV
Dialect and Table Schema naming wherever the concepts align. Datamonger
specifies them considerably more strictly than Frictionless does, since
Frictionless is not written for byte-exact determinism, but borrowing the names
buys ecosystem familiarity and interoperability, and avoids inventing a dialect
vocabulary from nothing.

Archive files such as ZIP and tarballs may be artifacts themselves. Extraction
happens only after hash verification and must reject absolute paths,
parent-directory traversal, unsafe links, duplicate output paths, and entries
exceeding defined file-count or expanded-size limits. These rules belong in the
shared decoder specification and conformance suite.

Datamonger does not silently perform statistical preprocessing such as
normalization, centering, imputation, one-hot encoding, or feature selection.
Such operations belong downstream unless they are explicitly part of the
registered definition of a particular dataset representation.

The registry therefore selects entries whose exact upstream artifacts can be
decoded by the initial format specifications. Repacking, cleaning, or
converting unsupported source files is not an implicit way around the format
and transformation limits. A future derived representation would need explicit
provenance, its own artifacts and recipe, and an identity distinct from the
original.

### Decoder version lifecycle

Because `decoder_version` is identity-bearing and datasets pin it, every
decoder version ever published would otherwise have to be implemented forever,
in three languages. That cost accumulates silently and must be bounded
deliberately.

The policy:

* Published decoder specification versions are immutable. A correction that can
  change logical output requires a new decoder version.
* A dataset adopts a new decoder version only by publishing a new dataset
  version.
* A registry release may **migrate** datasets, issuing new dataset versions that
  adopt the newer decoder and marking the old versions superseded.
* Once no dataset in any supported registry release references a decoder
  version, clients may drop support for it, and the specification records it as
  retired.

Superseded dataset versions remain resolvable from the registry releases that
contain them, so old code keeps working. What is bounded is the set of decoder
versions a current client must implement.

---

## Registry distribution

### Manifests are authored in YAML; clients never parse YAML

The editable manifests are canonical for humans and CI. Generated indexes are
canonical for clients.

Clients consume **only** the generated JSON index. They must never parse
manifest YAML.

This is normative because YAML across the three ecosystems is a genuine hazard.
R's `yaml` package and PyYAML implement YAML 1.1, in which `y`, `n`, `on`, and
`off` are booleans and unquoted version strings become numbers. The `version:
"1"` quoting in every example here is a symptom. If two clients ever parse a
manifest directly, they will eventually disagree about a value, and the
disagreement will be extremely hard to find. One sentence in the specification
removes the entire class of bug.

### Validation

CI validates manifests against JSON Schema and rejects at least:

* malformed identifiers;
* duplicate dataset versions;
* malformed hashes;
* missing required metadata;
* invalid artifact definitions;
* inconsistent registry entries;
* `modality` or `expect` shapes disagreeing with the representation;
* distribution policy disagreeing with retrieval locations;
* mutation of identity-bearing fields relative to any published release;
* mutation or removal of a published task definition;
* mutation or removal of a published component expectation;
* mutation or removal of a published verification record;
* a verification-record addition that is neither append-only nor well formed;
* an erratum that does not identify the affected release and record, preserve
  the original value, record its replacement, and carry maintainer approval.

### Releases

A registry release is immutable and versioned independently of the R, Python,
and Julia package releases. It fixes the complete index, including
default-version selections, task definitions, and catalog metadata.

A registry release is identified by **both** a release id and the SHA-256 of
its canonical index:

```text
release: 2026.08
index_sha256: "..."
```

Equivalent source trees must generate byte-identical indexes, which is what
makes the digest meaningful. The release descriptor is not part of the bytes it
hashes. Clients hash the exact downloaded index bytes before parsing them and
report both fields. After parsing, they also reject an index whose embedded
release id differs from the selector.

The pair `(release, index_sha256)` is the strong release selector. A release id
alone is only a convenience lookup: the client obtains its current digest from
a release catalog over HTTPS, and both the catalog and index are trusted only as
strongly as that TLS session. A server that replaces an index and its catalog
entry can therefore change what a bare release id resolves to. Documentation
must never describe a bare release id as a cryptographic pin.

Generated indexes are never edited manually.

### Distribution must not be coupled to package releases

Shipping the registry only inside client packages would mean that adding one
dataset requires a coordinated CRAN, PyPI, and Julia General release. CRAN in
particular has a strong social limit on release frequency. That would gate the
project's entire growth loop, the thing that determines whether anyone uses it,
behind the slowest of three release channels.

Fetching a pinned, immutable registry release over HTTPS is therefore part of
the MVP, not a later refinement:

* clients bundle a registry snapshot and its digest, which serves as an offline
  fallback and trust root for that snapshot only;
* clients can fetch a newer release by the strong `(release, index_sha256)`
  selector and reject it before parsing if the digest differs;
* clients may resolve a bare release id through the HTTPS release catalog as an
  explicit convenience operation, and must expose the resulting strong
  selector to the user;
* the active strong selector is settable per call, per session, and per project;
* a fetched release is cached like any other artifact;
* updates are always explicit. A client never silently changes the release it
  is using.

This preserves reproducibility when the strong selector is recorded, because
the index is identified by digest. A mutable branch such as `main`, a floating
"latest" alias, or a bare release-id lookup must never become an implicit source
of reproducibility-sensitive state. Per-project configuration records the
strong registry selector; future dataset lockfiles may additionally record the
resolved dataset versions and artifact digests used by an analysis.

The three clients ship the same registry release when making a coordinated
release, but they are no longer required to release in order to publish data.

### Trust

Until registry signing is implemented, the trust root is the registry snapshot
delivered through the client package or another explicitly configured trusted
channel. CRAN, PyPI, and the Julia General registry provide their own integrity
for that channel.

Possessing an index digest gives integrity relative to that digest; it provides
authentication only if the digest itself came through a trusted channel. A
strong selector copied from a paper, project configuration, or package snapshot
inherits the trust of that channel. A selector discovered from the release
catalog rests on TLS. The bundled snapshot does not authenticate later
snapshots, because there is no authenticated forward link between them.

SHA-256 therefore detects corruption or substitution relative to a trusted
selector. It does not authenticate a maliciously replaced registry and digest.
Documentation and security claims must preserve this distinction. Signed
release descriptors are the natural next step, and the index digest is the hook
they will attach to.

---

## Cross-language behavior

R, Python, and Julia implement the same registry semantics while remaining
idiomatic within their ecosystems.

Cross-language consistency is defined relative to the same registry release and
supported specification versions. Explicit dataset identifiers must resolve to
the same identity-bearing artifacts and representation in every registry
release that contains them. Release-scoped metadata and verification records
may differ only under the append-only and erratum rules above. Defaults may
differ between registry releases, which is why unversioned calls must report
both the resolved identifier and registry release.

The clients share conformance fixtures verifying, at minimum, that they:

* resolve the same dataset and version;
* report the same registry release, index digest, and canonical identifier;
* reject a registry index that does not match its strong selector and label a
  bare release-id lookup as TLS-trusted rather than pinned;
* resolve the same artifact hashes;
* hash the same stored bytes despite HTTP transfer and content-coding behavior;
* follow the same retrieval-location fallback rules;
* detect corrupt downloads;
* publish safely when concurrent processes request the same artifact and avoid
  eviction while an artifact is being published or read;
* use cached artifacts offline;
* interpret registry metadata consistently;
* reject unsupported schema and decoder versions;
* produce byte-identical canonical logical forms, including validity padding,
  invalid-value storage, dense and sparse ordering, and numeric edge cases;
* verify decoded values by default and report an explicit opt-out as
  artifact-only verification;
* classify failures according to the shared error taxonomy.

Tiny local fixtures and a local HTTP test server are used for hermetic CI
rather than large external datasets. The local server must be able to simulate
transfer encodings, content encodings, truncation, corruption, and location
failure. Golden results are stored as canonical logical forms, so each client
is tested against the specification rather than against another client's
output.

The packages remain relatively lightweight. Heavy dataframe or machine-learning
dependencies are optional wherever possible.

---

## Operations

Two operational pieces are part of the MVP, not the long term, because they are
what makes the promise real and what makes the registry grow.

### `dm-add`

A manifest authoring tool. Given a URL, it downloads, hashes, sizes, detects
declared and actual compression, checks for the mislabeled-`Content-Encoding`
hazard, decodes with a proposed representation, computes candidate verification
records and expected shapes, and drafts a manifest for review. Its output is an
authoring aid, not an independent attestation; the stable-release publication
rule under [`expect`](#the-expect-block) still applies.

Without it, the first thirty manifests are written by hand, every external
contributor gets the hashes wrong, and the barrier to adding a dataset is high
enough that nobody does. It is the actual growth loop and deserves the same
tests and review as a client decoder.

### `dm-canary`

A scheduled job that re-fetches every registered upstream location, checks that
it still serves the registered bytes, re-decodes with each released independent
implementation, verifies a supported canonical digest, and opens an issue when
anything drifts. Implementations may be sharded across runs, but every stable
dataset and client combination is checked on a documented schedule.

This is the operational core of the entire promise. It is also how the project
learns which datasets have actually rotted and therefore which ones justify the
eventual cost of mirroring. It runs separately from hermetic CI, on a schedule,
and its failures are expected and informative rather than alarming. Canary
status informs availability; it must not be presented as preservation.

---

## MVP

The target MVP is a substantial version 1, not the smallest experiment that can
test the idea. Before committing to its complete surface, build one narrow
vertical proof:

* one reference client;
* one small CSV dataset and one small LIBSVM dataset;
* a provisional schema and canonical-form version;
* one remote registry index fetched with a strong
  `(release, index_sha256)` selector;
* end-to-end artifact and default-on decoded verification.

The proof may use a prerelease registry, omit cache management, and support only
single-process cache publication. Its purpose is to expose mistakes in identity,
numeric parsing, canonical hashing, and release selection before those choices
become three-language protocols. The artifacts and formats below describe the
full MVP after that proof succeeds.

Sources:

```text
LIBSVM
UCI
```

Roughly ten datasets, covering regression, binary classification, multiclass
classification, unsupervised data, dense data, sparse data, and at least one
multi-artifact train and test split.

Formats:

```text
CSV
TSV
LIBSVM / SVMLight
```

Operations, in the reference client first and then ported:

```text
fetch_data()
fetch_artifact()
data_info()
list_data()
cache_info()
cache_clean()
```

Implement:

* a normative specification covering identity, retrieval, the canonical logical
  form, the index, and decoder contracts;
* immutable, digest-identified, independently versioned registry releases,
  fetchable and pinnable from day one;
* a bundled registry snapshot as offline fallback and trust root for that
  snapshot;
* registry resolution;
* local caching with explicit user consent and manual management;
* SHA-256 verification of artifacts;
* default-on, versioned canonical-digest verification of decoded results;
* atomic downloads and cache publication safe against concurrent publishers,
  readers, and cleaners;
* deterministic retrieval-location fallback;
* offline reuse;
* decoding with explicit representation recipes;
* stable per-client return types;
* the shared error taxonomy and conformance suite;
* `dm-add`, `dm-index`, and `dm-canary`.

Do not initially implement:

* Datamonger-controlled mirroring or a preservation guarantee;
* OpenML as a source;
* user uploads, accounts, or a web application;
* arbitrary private datasets;
* data transformations;
* model storage or benchmarking;
* sophisticated search;
* registry signing;
* dataset lockfiles beyond the strong registry selector in project
  configuration;
* huge-data streaming;
* Kaggle;
* categorical, temporal, or decimal logical types.

### Milestones

0. **Vertical proof.** Exercise one CSV and one LIBSVM dataset through one
   reference client and one strongly selected remote prerelease index. Expect to
   revise or discard the provisional formats.
1. **Specification.** Registry schema, identity rules, canonical logical form,
   decoder contracts, deterministic index generator, an immutable test registry
   release, exhaustive golden fixtures, and malformed-input cases.
2. **Reference client, retrieval.** Registry resolution, strong release
   fetching and pinning, `fetch_artifact()`, hashing, fallback, concurrent
   caching, corruption, and offline behavior, with the hermetic test server.
3. **Reference client, decoding.** One decoder end to end, canonical form
   emission, `expect` verification, then the remaining initial decoders and
   multi-artifact assembly.
4. **Tooling and candidate data.** Build `dm-add` and `dm-canary`; author and
   review ten real manifests across LIBSVM and UCI in a prerelease registry; run
   end-to-end retrieval separately from hermetic CI. Candidate verification
   records are not yet stable attestations.
5. **Freeze candidate.** Cut a feature-frozen specification revision 1 release
   candidate. Corrections found during independent implementation produce a new
   candidate rather than silently changing the contract.
6. **Port, certify, and freeze.** Implement the Python and Julia clients from the
   candidate specification, driven by the conformance suite. Independently
   reproduce the verification records for every candidate dataset, resolve
   discrepancies, then freeze specification revision 1 and cut the first stable
   registry release. Only that release claims cross-language verification.

Milestones 0 through 5 avoid triplicating a moving design. Milestone 6 pays the
cost of independent implementations only after the contracts have survived a
real vertical proof and reference use. Stable publication waits for that
independence, so the reference implementation never certifies its own output.

---

## Longer-term direction

Potential later additions, driven by actual use rather than designed up front:

* durable Datamonger-controlled preservation copies, initially on Zenodo and
  prioritized by canary evidence;
* OpenML and other provider adapters;
* signed registry releases, anchored on the index digest;
* project lockfiles;
* richer logical types and task definitions;
* additional modalities;
* authenticated upstream providers;
* command-line tools;
* additional language clients;
* a shared native decoding core, if conformance drift justifies it.

Datamonger's value ultimately rests on a precise promise:

> A researcher can identify data independently of its location, detect any
> change in its bytes or interpretation, and decode available registered bytes
> the same way years later and in another language. When Datamonger reports a
> preservation copy, retrieval does not depend on the original provider.

Dataset acquisition should become boring, stable infrastructure. The fastest
route there is being boring in fewer places at once.
