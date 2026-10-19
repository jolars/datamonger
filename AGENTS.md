# Repository Guidelines

## Project Structure & Module Organization

The Python client lives in `packages/python`; the R and Julia clients
live in `packages/r` and `packages/julia`; the standalone Rust CLI lives in
`packages/cli`. The reusable Rust decoder lives in `crates/datamonger-core`;
Python binds it through PyO3 and Maturin, and the R adapter vendors its published
crates.io release and uses extendr bindings.
Python library code is under `packages/python/src/datamonger`; hermetic tests are
beside each client, and network-dependent smoke tests are isolated in each
client's `tests_live` directory.
Dataset manifests and release indexes belong in `registry/`; format contracts
belong in `spec/`. Curated dataset recipes, documentation, and deposit receipts
belong in `curation/<name>/<version>/`; shared tooling belongs in `tools/`.
Keep maintainer instructions in `README.md` and deposited dataset documentation
in `DATASET.md`. Store source and generated data outside the working tree.
Use `tools/dm_index.py` to validate generated registry data.
Consult `DESIGN.md` for architecture.

## Build, Test, and Development Commands

Enter the repository's devenv shell before development. The main quality gate
matches CI:

```console
devenv test
```

See [CONTRIBUTING.md](CONTRIBUTING.md#development-environment) for focused
commands and live-source checks. Run live checks only when network access and
upstream availability are expected.

Use `dm-test-r` to test the R adapter against local core edits. Run `dm-vendor-r`
after updating published Rust dependencies and `dm-document-r` after R binding
changes. See `CONTRIBUTING.md` for release ordering and MSRV checks.

The CLI bundles stable registry assets in `packages/cli/assets`; `devenv test`
checks them against their selected registry release and `spec/schema`.

## Coding Style & Naming Conventions

Target Python 3.11 or newer. Use four-space indentation, Ruff formatting with
an 88-character line limit, and the configured `B`, `E`, `F`, `I`, `RUF`,
`SIM`, and `UP` lint rules. Keep public APIs typed; strict mypy must pass. Use
`snake_case` for modules, functions, and variables, and `PascalCase` for types.
For R, use two-space indentation and `snake_case`; keep exported interfaces and
S3 return classes documented. For Julia, follow idiomatic four-space formatting,
use `snake_case` for functions and variables, and use `PascalCase` for types.

Prefer lowercase names with hyphens between words and variant suffixes for new
datasets (for example, `rcv1-binary`). Preserve the provider's spelling in
`provenance.upstream_name`.

## Testing Guidelines

Use pytest for Python, testthat for R, and `Test` for Julia. Add regression tests
beside the affected client, prefer existing fixtures, and keep routine tests
deterministic and offline. The R and Julia packages copy the small shared corpus
into their package tests; `devenv test` verifies those copies against
`tests/conformance`. No coverage threshold is configured; cover new branches
and failure modes directly.

## Commit & Pull Request Guidelines

Follow the repository's Conventional Commit history, such as `feat: add ...`,
`fix: validate ...`, `test: share ...`, and `docs: update ...`. Keep subjects
short and imperative. Pull requests should explain the behavioral change, link
relevant issues, note registry or specification effects, and include tests.
Before requesting review, run `devenv test` and report any intentionally skipped
live-source checks.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
