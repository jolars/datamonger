# Datamonger MVP Roadmap

This roadmap turns the architecture in [DESIGN.md](DESIGN.md) into ordered,
testable slices. Check an item only when its tests and exit criteria pass.

## Project decisions

- [x] Use Python as the reference client.
- [x] Keep `fetch_data()` as the shared primary API name.
- [x] Return pandas data frames from the Python delimited-text decoder and make
  pandas a required dependency.
- [x] Use devenv for the development environment, uv for dependency management,
  and Hatchling as the Python build backend.
- [x] License project code under MIT.
- [x] Publish prerelease registry indexes through GitHub Releases; never publish
  dataset artifacts there.
- [x] Treat every verification record as provisional until an independent
  implementation reproduces it.

## Slice 0A: Python CSV spine

- [x] Configure the Python package, uv lockfile, and devenv quality gate.
- [x] Specify the provisional index, delimited-text subset, and canonical vector
  encoding used by the proof.
- [x] Add a synthetic mixed-type CSV fixture and fixed canonical golden digest.
- [x] Fetch and verify a strongly selected registry index before parsing it.
- [x] Resolve explicit and default dataset versions.
- [x] Fetch, size-check, hash, and atomically cache one upstream-only artifact.
- [x] Reverify cached bytes and reuse them without network access.
- [x] Decode explicitly typed CSV columns without type inference.
- [x] Compute the canonical digest from an explicit logical-value model.
- [x] Verify decoded values by default and report an explicit artifact-only
  opt-out.
- [x] Expose `fetch_data()`, `Registry`, `FetchInfo`, and `FetchResult`.
- [x] Pass formatting, linting, typing, unit tests, and package-build checks.

Exit criterion: a cold-cache call and a warm-cache call with the server offline
return the same verified pandas data frame, and `devenv test` passes without
external network access.

## Slice 0B: Complete the vertical proof

- [x] Specify canonical sparse matrices without changing the published vector
  encoding; otherwise increment the provisional canonical-form version.
- [x] Implement the provisional LIBSVM decoder and sparse result type.
- [x] Author upstream-only manifests for UCI Iris and LIBSVM `heart_scale`.
- [x] Generate a prerelease index and publish it as a GitHub Release asset.
- [x] Fetch one real CSV and one real LIBSVM dataset through that index.
- [x] Run live-source smoke tests separately from hermetic CI.

Exit criterion: both real datasets pass artifact and decoded verification when
fetched through one strongly selected remote prerelease index.

## Milestone 1: Specification and registry

- [x] Complete the normative identity, retrieval, index, and canonical-form
  specifications.
- [x] Complete versioned CSV, TSV, and LIBSVM decoder contracts.
- [x] Add JSON Schemas for manifests, generated indexes, releases, and errata.
- [x] Implement deterministic `dm-index` output and immutable release checks.
- [x] Add an immutable local test registry release and exhaustive golden,
  malformed-input, property, and fuzz-derived cases.

Exit criterion: equivalent source trees generate byte-identical indexes; the
reference client passes registry and canonical-form conformance; and the shared
decoder corpus is complete for activation in Milestone 3.

## Milestone 2: Python retrieval

- [x] Bundle a registry snapshot and its trusted digest.
- [x] Support strong selectors per call, session, and project.
- [x] Add explicit bare-release catalog lookup and expose the resolved digest.
- [x] Implement `fetch_artifact()` and deterministic location fallback.
- [x] Implement HTTP content-coding and transfer semantics from the specification.
- [x] Add concurrent publisher, reader, and cleaner leases with crash recovery.
- [x] Implement offline behavior, `cache_info()`, and `cache_clean()`.
- [x] Complete the shared semantic error taxonomy and hermetic HTTP simulations.

Exit criterion: retrieval, corruption, concurrency, cache, and offline tests pass
against the local HTTP server without live network access.

## Milestone 3: Python decoding

- [x] Activate complete CSV and TSV conformance and compression handling.
- [x] Activate complete LIBSVM/SVMLight conformance and multi-artifact split
  assembly.
- [ ] Implement stable return types for all initial representations.
- [ ] Implement `data_info()` and `list_data()`.
- [ ] Verify decoded results by default for every initial decoder.
- [ ] Complete Python conformance fixtures and malformed-input coverage.

Exit criterion: every initial representation passes golden canonical-form and
round-trip registry tests.

## Milestone 4: Tooling and candidate data

- [ ] Build `dm-add` around the reference decoder and authoring checks.
- [ ] Build `dm-canary` and a scheduled upstream-verification workflow.
- [ ] Curate roughly ten UCI and LIBSVM entries covering regression, binary and
  multiclass classification, unsupervised data, dense and sparse data, and a
  multi-artifact train/test split.
- [ ] Review provenance, licensing, shapes, names, and representative values.
- [ ] Publish candidate records only in prerelease registries.

Exit criterion: every candidate is hermetically valid and passes scheduled live
retrieval with the reference client.

## Milestone 5: Specification release candidate

- [ ] Freeze the revision 1 feature set and version every contract.
- [ ] Finish user, package, contributor, trust, and operations documentation.
- [ ] Cut a feature-frozen specification and registry release candidate.
- [ ] Require a new release candidate for every output-affecting correction.

Exit criterion: the candidate is complete enough to implement without consulting
the Python source.

## Milestone 6: Port, certify, and freeze

- [ ] Implement the R client against the release candidate and address CRAN cache
  consent and packaging constraints.
- [ ] Implement the Julia client against the corrected release candidate.
- [ ] Run all three clients through the shared conformance suite.
- [ ] Independently reproduce and review every candidate verification record.
- [ ] Freeze specification revision 1 and publish the first stable registry.
- [ ] Release coordinated R, Python, and Julia clients using the same snapshot.

Exit criterion: the same strong registry selector yields identical canonical
logical forms in R, Python, and Julia.
