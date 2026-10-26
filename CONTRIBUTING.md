# Contributing to Datamonger

Datamonger accepts changes to clients, normative contracts, conformance data,
registry records, and operational tooling. These surfaces have different review
obligations because a small code or metadata edit can alter the data returned by
every implementation.

By contributing code or documentation, you agree that your contribution is
licensed under the repository's MIT license. Upstream dataset artifacts are not
part of that license and must not be committed to this repository; small,
purpose-built conformance fixtures belong under `tests/conformance/artifacts`.

## Before changing behavior

Read the document that owns the behavior:

- [`spec/revision-1.md`](spec/revision-1.md) inventories the frozen revision 1
  contracts and defines their version boundaries.
- [`spec/`](spec/README.md) is normative for clients, registry tooling, and
  conformance behavior.
- [`tests/conformance/README.md`](tests/conformance/README.md) defines the
  language-neutral implementation corpus.
- [`TRUST.md`](TRUST.md) constrains integrity, authentication, licensing, and
  preservation claims.
- [`OPERATIONS.md`](OPERATIONS.md) defines publication and incident procedures.
- [`DESIGN.md`](DESIGN.md) records rationale; it does not override a normative
  contract.

Revision 1 is frozen and stable. Discuss a proposed contract extension before
implementing it. An editorial clarification may keep the current contract
version only when it changes no accepted input, logical output, identity,
retrieval behavior, or failure classification. Output-affecting changes need the
later revision and contract versions described by the specification.

## Development environment

The supported environment is the repository's devenv shell. From the repository
root, run:

```console
devenv shell
devenv test
```

Entering the shell installs Git hooks for Ruff, nixfmt, and Prettier. The hooks
format staged Python and Nix files and YAML under `.github` plus `devenv.yaml`.
Generated registry files and conformance fixtures are outside the YAML formatter's
scope. Run `prek run --all-files` to check all matching files; formatters may
update files, so review and stage their changes before committing. `devenv test`
also runs these hooks, and CI checks YAML formatting with Prettier.

The quality gate checks formatting, lints Python, type-checks the package and
tools, runs the Rust CLI and all three hermetic language client suites, checks
generated registry data and shared fixture synchronization, builds the Python
and R distributions, and runs a CRAN-style R package check. Focused commands
from `packages/python` are:

```console
uv run pytest
uv run pytest tests/test_decoder.py
ruff format . ../../tools ../../curation
ruff check . ../../tools ../../curation
uv run mypy
uv run python ../../tools/dm_index.py check
uv build
```

Python uses Maturin to build the private PyO3 extension. `uv sync` builds it
against the local `crates/datamonger-core` path dependency, and `uv build` bundles
that core in the source distribution and builds a wheel from it. After editing
Rust code, run `uv sync --reinstall-package datamonger` before Python tests to
rebuild the extension. The binding uses the repository's stable Rust toolchain;
the core and R adapter retain their separate MSRV checks. Python source
releases include the local core, so they do not require an earlier crates.io
publication. When changing the core's version, update the Python and C ABI
bindings' Cargo requirements and lockfiles in the same change.

From `packages/python`, check the bindings and compare them with the independent
Python implementation retained under `tests/reference`:

```console
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
uv run pytest tests/test_native.py
```

The Python oracle is test-only. Keep its parsing and canonical encoding
independent of the native backend. The differential tests compare native and
Python results against the shared conformance corpus, compressed inputs,
malformed artifacts, and generated inputs before a backend change can ship.
CI also builds portable wheels for all supported platforms, installs them into
fresh environments, and tests those installed distributions. The release
workflow reuses the same build and test workflow.

Focused commands from `packages/r` are:

```console
Rscript -e 'testthat::test_local(".")'
R CMD build .
R CMD check --as-cran datamonger_*.tar.gz
```

The Rust core has MSRV 1.82 and its own toolchain, separate from the CLI. From
the repository root, use the pinned compiler through devenv:

```console
dm-core-cargo test --locked --manifest-path crates/datamonger-core/Cargo.toml
dm-core-cargo clippy --locked --manifest-path crates/datamonger-core/Cargo.toml --all-targets -- -D warnings
dm-core-cargo doc --locked --manifest-path crates/datamonger-core/Cargo.toml --no-deps
```

The R adapter depends on a published `datamonger-core` version from crates.io.
Use `dm-test-r` to test it against unpublished core edits. For other development
scripts, use `dm-local-r` in place of `Rscript`; it sets `DM_R_CORE_PATH` and
enables a local Cargo patch. These commands temporarily match the dependency pin
to the local core version and restore the release manifest and lockfile afterward.
For example, from `packages/r`, run:

```console
dm-local-r -e 'pkgload::load_all(".")'
```

Normal source builds use the published version and compile offline with a locked
dependency graph. Local builds use Cargo's usual cache and may download new
dependencies. Release builds use at most two Cargo jobs. `DEBUG=1` selects a
debug build; `NOT_CRAN=1` permits development without the vendor archive.

Publish core changes before preparing an R release that needs them. Update the
R adapter's version requirement when needed, then run `dm-vendor-r`. That command
resolves the published core, runs `rextendr::vendor_crates()`, and records the
lockfile digest. Commit the lockfile, vendor archive, vendor configuration, and
digest. The core receives the same vendoring treatment as every other registry
dependency. The R tarball must build with no checkout or Cargo network access.

Run `python tools/dm_rust_sources.py` after shared conformance changes to update
the core's fixture copy. `python tools/dm_rust_sources.py --check` checks fixtures
and vendor metadata. Check changes with Rust 1.82.

Run `dm-document-r` after changing extendr function signatures or Rust wrapper
documentation. It generates the private R wrappers directly from extendr
metadata without replacing the package's manually maintained Rd files or
NAMESPACE. Do not edit the generated wrappers by hand.

Versionary manages core releases independently of the language clients. Merge
its release PR after CI passes. Versionary creates a published GitHub Release
with a `datamonger-core-v<version>` tag, which triggers `Publish Rust core`.
That workflow verifies the tag and crate versions, tests and packages the crate
with Rust 1.82, and publishes to crates.io through trusted publishing. See
`OPERATIONS.md` for the publisher configuration.

After the crate is published, update the R lockfile and vendor archive:

```console
dm-core-cargo update --manifest-path packages/r/src/rust/Cargo.toml -p datamonger-core
dm-vendor-r
```

The R release continues to use its committed dependency version until this
refresh is reviewed and merged.

Julia uses the C ABI in `crates/datamonger-ffi`, with Rust 1.82 or newer. Build
and install a local native artifact from the repository root before testing:

```console
julia tools/dm_julia_core.jl
```

The build uses the pinned core compiler in devenv. It writes an ignored local
artifact binding under `packages/julia/deps`, leaving the release manifest
unchanged. Rebuild after editing the core or C ABI. `DM_JULIA_CORE_LIBRARY` can
instead select an absolute shared-library path for development. Julia checks its
ABI version on first use. Registry and metadata operations do not load it.

The focused Julia command from `packages/julia` is:

```console
julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.test()'
```

The original Julia decoder and canonical encoder live under
`packages/julia/test/reference` and are test-only. Keep them independent of the
native implementation. `test_native.jl` compares typed values, missingness,
return types, canonical bytes, errors, compression behavior, and generated edge
cases. The shared corpus remains the normative source for golden values. HTTP
content decoding remains Julia's responsibility, separate from native artifact
decompression.

CI packages native libraries for Linux x86-64 and ARM64 with glibc 2.17 or newer,
macOS Intel and Apple Silicon, and Windows x86-64. It tests each installed
artifact with Julia 1.10 and the current stable Julia, outside the checkout,
without building Rust. See `OPERATIONS.md` for native release ordering.

Focused CLI commands from `packages/cli` are:

```console
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked --example generate_cli_docs -- --check
```

The CLI reference is generated from `packages/cli/src/cli.rs` with clapdown.
After changing commands or help text, run
`cargo run --locked --example generate_cli_docs` from `packages/cli` and commit
`documentation/pages/cli-reference.md`. CI and `devenv test` check that it is current.

From `packages/python`, run the live proof-registry test separately:

```console
uv run pytest tests_live/test_proof_registry.py
```

Run the R and Julia `tests_live/test_candidate_registry.*` scripts separately
from `packages/r` and `packages/julia`, respectively, to retrieve and verify
every record in the published candidate registry. Pass `2026.09` as the first
argument to audit the stable registry instead.

Live-source tests and canaries require network access and healthy upstreams.
They are not substitutes for deterministic tests and are not part of the routine
hermetic gate.

## Code changes

Prefer test-driven changes. Put deterministic tests under the affected client,
reuse fixtures where possible, and simulate HTTP behavior rather than requiring
network access. Put unavoidable network checks in a separately invoked live
suite.

When behavior is shared across languages, add or update a language-neutral case
under `tests/conformance` before making a client-specific implementation pass
it. A conformance case must identify the contract version it exercises and must
contain language-neutral expected values or bytes.

Public APIs must be typed, strict mypy must pass, and Python code must satisfy
Ruff with the configured 88-character line limit. Comments should explain why a
constraint exists, not narrate the code.

## Adding or revising a dataset

Never commit downloaded upstream dataset artifacts. Manifests record upstream or
reviewed mirror locations and the digests of the bytes served there.

1. Choose a canonical `(source, name, version)` identity. For new curated
   datasets, follow the [curated dataset naming policy](#curated-dataset-names).
   If artifact identity or the complete representation recipe differs from a
   published record, use a new dataset version.

2. Draft a YAML manifest from
   [`spec/schema/manifest-v5.schema.json`](spec/schema/manifest-v5.schema.json).
   Supply descriptive, provenance, license, artifact, location, decoder, and
   task metadata. Do not guess a license—use `status: unknown` when the evidence
   is insufficient.

   Record [preprocessing](spec/preprocessing.md) separately for upstream and
   Datamonger preparation. Supply known steps, parameters, and evidence. Use
   `unknown` when the history is not established; reserve `none` for an absence
   of preprocessing supported by evidence.

3. Let `dm-add` retrieve every location, verify that they serve identical bytes,
   decode the data, and derive retrieval facts and candidate expectations:

   ```console
   cd packages/python
   uv run python ../../tools/dm_add.py path/to/draft.yaml \
     --output ../../registry/datasets/<source>/<name>-<version>.yaml
   ```

   `dm-add` writes the completed manifest to stdout by default and a bounded
   review report to stderr. `--force` replaces an output only when that
   replacement is intentional. Generated verification is an authoring aid, not
   an independent attestation.

4. Review the upstream landing page, authorship and citation, version identity,
   license evidence, distribution and preservation status, every decoded name
   and shape, task roles, and the representative values printed by `dm-add`.
   Check for IDs or bookkeeping columns that should not silently become model
   features.

5. Add the manifest and its default to `registry/collection.yaml`. Do not edit
   generated indexes or selectors, and do not alter a published release.

6. Commit the registry change with `feat(registry): ...` or
   `fix(registry): ...`. Versionary prepares the release PR and its generated
   snapshot as described in [OPERATIONS.md](OPERATIONS.md). Review and
   independently verify the new records before merging that PR; the publisher
   re-fetches manifests before publishing and runs the canary against the
   published asset afterward.

A release-scoped metadata improvement may retain a dataset version only when it
obeys the append-only evolution rules in [`spec/identity.md`](spec/identity.md).
Incorrect component expectations or verification records require an approved
erratum in a later registry release; earlier release bytes remain unchanged.

### LIBSVM decoder version 2

Use manifest schema 5 and `decoder_version: 2` for LIBSVM artifacts that
explicitly store zero-valued features. The decoder omits those entries while
preserving the exact downloaded bytes for artifact verification. See
[`spec/decoders/libsvm-v2.md`](spec/decoders/libsvm-v2.md).

The R adapter's published vendor archive currently contains core 0.1.0 and
supports decoder v1. Use `dm-test-r` to exercise v2 against the local core.
Before releasing R support for v2, publish the updated core, update the R
core dependency, enable its v2 dispatch for that dependency, and run
`dm-vendor-r`. Julia likewise needs a native artifact containing the new
v2 entry points; `tools/dm_julia_core.jl` builds it locally. Do not release
a registry selecting v2 until the affected client releases are available.

### Curated dataset names

For new datasets curated and distributed under the `datamonger` source
namespace, use `<surname><year>[<paper-letter>][-<dataset-label>]`. Use the
first author's surname normalized to lowercase ASCII and the paper's
publication year. Preserve the provider's spelling in `provenance.upstream_name`.

| Situation | Dataset name |
| --- | --- |
| One paper, one dataset | `smith2023` |
| Multiple distinct datasets from that paper | `smith2023-plasma`, `smith2023-tissue` |
| Another paper with the same first-author surname and publication year | `smith2023b` |
| Multiple distinct datasets from that second paper | `smith2023b-plasma`, `smith2023b-tissue` |

The first paper registered with a surname and year uses the unsuffixed base.
For subsequent papers with the same base, assign the next available letter
starting with `b`, then `c`, and so on. Reuse that paper's base and letter for
all its datasets. These letters identify papers within the registry and are
independent of bibliography labels. Check existing manifests, curation
directories, and published indexes before allocating a name.

For distinct datasets from one paper, prefer short suffixes describing their
scientific content. When no useful descriptive label exists, use a stable
source label such as `-table-s2`. Avoid bare numeric suffixes such as `-1`:
dataset versions already have a separate field, written as `@1` in the
canonical ID. Multiple tasks or training and test splits alone generally
belong within one dataset.

Keep existing dataset IDs unchanged when adding papers or datasets. If a
second dataset is discovered after an unsuffixed name is established, retain
that name and give the new dataset a descriptive suffix. This policy applies
to new curated names; existing IDs and names in upstream source namespaces
retain their established spelling.

## Registry and specification changes

Treat the following as separate questions during review:

- Does the dataset identity change?
- Does any accepted input or decoded logical output change?
- Do canonical bytes or error precedence change?
- Is the edit release-scoped metadata that the evolution rules permit?
- Does the change require a new schema, decoder, canonical-form, behavioral
  contract, dataset, registry release, or specification release candidate?

`dm-index` compares repeated dataset identities with every lower-sequence
release and rejects forbidden mutations. Passing that check is necessary, but it
does not replace semantic review.

Normative prose, JSON Schemas, conformance descriptors, reference-client
behavior, and package documentation must agree. A pull request that changes a
contract should update every affected surface together and explain the version
decision.

## Pull requests

Keep changes focused and use a Conventional Commit subject. In the pull request
description:

- explain the user-visible or protocol-visible effect;
- link the relevant issue;
- state which contract and registry versions are affected;
- identify any dataset identity, licensing, distribution, or preservation
  consequence;
- list conformance and client tests added or changed;
- report `devenv test`; and
- report separately any live checks run or intentionally skipped.

Reviewers should be able to reproduce generated files and understand every trust
claim without consulting an unrecorded discussion.
