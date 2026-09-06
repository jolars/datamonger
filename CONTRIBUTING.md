# Contributing to Datamonger

Datamonger accepts changes to clients, normative contracts, conformance data,
registry records, and operational tooling. These surfaces have different
review obligations because a small code or metadata edit can alter the data
returned by every implementation.

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

Revision 1 is feature-frozen. Discuss a proposed contract extension before
implementing it. An editorial clarification may keep the current contract
version only when it changes no accepted input, logical output, identity,
retrieval behavior, or failure classification. Output-affecting changes need
the versions and release-candidate treatment described by the specification.

## Development environment

The supported environment is the repository's devenv shell. From the repository
root, run:

```console
devenv shell
devenv test
```

The quality gate formats and lints Python, type-checks the package and tools,
runs the hermetic test suite, checks generated registry data, and builds the
Python distribution. Focused commands from `packages/python` are:

```console
uv run pytest
uv run pytest tests/test_decoder.py
ruff format . ../../tools
ruff check . ../../tools
uv run mypy
uv run python ../../tools/dm_index.py check
uv build
```

Live-source tests and canaries require network access and healthy upstreams.
They are not substitutes for deterministic tests and are not part of the
routine hermetic gate.

## Code changes

Prefer test-driven changes. Put deterministic Python tests in
`packages/python/tests`, reuse fixtures where possible, and simulate HTTP
behavior with the local test server. Put unavoidable network checks in
`packages/python/tests_live`.

When behavior is shared across languages, add or update a language-neutral case
under `tests/conformance` before making a client-specific implementation pass
it. A conformance case must identify the contract version it exercises and
must contain language-neutral expected values or bytes.

Public APIs must be typed, strict mypy must pass, and Python code must satisfy
Ruff with the configured 88-character line limit. Comments should explain why
a constraint exists, not narrate the code.

## Adding or revising a dataset

Never commit downloaded upstream dataset artifacts. Manifests record upstream
or reviewed mirror locations and the digests of the bytes served there.

1. Choose a canonical `(source, name, version)` identity. If artifact identity
   or the complete representation recipe differs from a published record, use a
   new dataset version.
2. Draft a YAML manifest from
   [`spec/schema/manifest-v1.schema.json`](spec/schema/manifest-v1.schema.json).
   Supply descriptive, provenance, license, artifact, location, decoder, and
   task metadata. Do not guess a license—use `status: unknown` when the evidence
   is insufficient.
3. Let `dm-add` retrieve every location, verify that they serve identical
   bytes, decode the data, and derive retrieval facts and candidate
   expectations:

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
5. Add the manifest to a new, unpublished release source under
   `registry/releases`. Do not edit a generated `index.json` or `selector.json`
   and do not alter an already published release.
6. Build and check the new release as described in
   [OPERATIONS.md](OPERATIONS.md). Re-fetch changed manifests before publication,
   and run the canary against the published asset afterward.

A release-scoped metadata improvement may retain a dataset version only when it
obeys the append-only evolution rules in
[`spec/identity.md`](spec/identity.md). Incorrect component expectations or
verification records require an approved erratum in a later registry release;
earlier release bytes remain unchanged.

## Registry and specification changes

Treat the following as separate questions during review:

- Does the dataset identity change?
- Does any accepted input or decoded logical output change?
- Do canonical bytes or error precedence change?
- Is the edit release-scoped metadata that the evolution rules permit?
- Does the change require a new schema, decoder, canonical-form, behavioral
  contract, dataset, registry release, or specification release candidate?

`dm-index` compares repeated dataset identities with every lower-sequence
release and rejects forbidden mutations. Passing that check is necessary, but
it does not replace semantic review.

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

Reviewers should be able to reproduce generated files and understand every
trust claim without consulting an unrecorded discussion.
