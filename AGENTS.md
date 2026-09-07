# Repository Guidelines

## Project Structure & Module Organization

The Python reference client lives in `packages/python`; the R and Julia clients
live in `packages/r` and `packages/julia`. Python library code is under
`packages/python/src/datamonger`; hermetic tests are beside each client, and
network-dependent smoke tests are isolated in each client's `tests_live`
directory.
Dataset manifests and release indexes belong in `registry/`; format contracts
belong in `spec/`. Use `tools/dm_index.py` to validate generated registry data.
Consult `DESIGN.md` for architecture and `TODO.md` for the active roadmap.

## Build, Test, and Development Commands

Enter the repository's devenv shell before development. The main quality gate
matches CI:

```console
devenv test
```

From `packages/python`, focused commands are:

- `uv run pytest`—run the hermetic unit suite.
- `uv run pytest tests/test_decoder.py`—run one test module.
- `ruff format . ../../tools`—format Python sources and tooling.
- `ruff check . ../../tools`—run lint checks.
- `uv run mypy`—type-check the package and registry builder in strict mode.
- `uv run python ../../tools/dm_index.py check`—verify checked-in production
  release indexes.
- `uv build`—build the Python distribution.

From `packages/r`, focused commands are:

- `Rscript -e 'testthat::test_local(".")'`—run hermetic R tests.
- `R CMD build .`—build the R source package.
- `R CMD check --as-cran datamonger_*.tar.gz`—run CRAN-style checks.

From `packages/julia`, focused commands are:

- `julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.test()'`—run the
  hermetic Julia suite.
- `julia --project=. tests_live/test_candidate_registry.jl`—audit the published
  candidate when network access is expected.

Run `uv run pytest tests_live/test_proof_registry.py` only when network access
and upstream availability are expected. The R and Julia candidate audits are
the corresponding `tests_live/test_candidate_registry.*` scripts.

## Coding Style & Naming Conventions

Target Python 3.11 or newer. Use four-space indentation, Ruff formatting with
an 88-character line limit, and the configured `B`, `E`, `F`, `I`, `RUF`,
`SIM`, and `UP` lint rules. Keep public APIs typed; strict mypy must pass. Use
`snake_case` for modules, functions, and variables, and `PascalCase` for types.
For R, use two-space indentation and `snake_case`; keep exported interfaces and
S3 return classes documented. For Julia, follow idiomatic four-space formatting,
use `snake_case` for functions and variables, and use `PascalCase` for types.

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
