# Repository Guidelines

## Project Structure & Module Organization

The Python reference client lives in `packages/python`. Library code is under
`packages/python/src/datamonger`, hermetic tests are in `packages/python/tests`,
and network-dependent smoke tests are isolated in `packages/python/tests_live`.
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

Run `uv run pytest tests_live/test_proof_registry.py` only when network access
and upstream availability are expected.

## Coding Style & Naming Conventions

Target Python 3.11 or newer. Use four-space indentation, Ruff formatting with
an 88-character line limit, and the configured `B`, `E`, `F`, `I`, `RUF`,
`SIM`, and `UP` lint rules. Keep public APIs typed; strict mypy must pass. Use
`snake_case` for modules, functions, and variables, and `PascalCase` for types.

## Testing Guidelines

Use pytest. Name files `test_*.py` and tests `test_<behavior>`. Add regression
tests alongside the affected module, prefer existing fixtures in
`tests/fixtures`, and keep routine tests deterministic and offline. No coverage
threshold is configured; cover new branches and failure modes directly.

## Commit & Pull Request Guidelines

Follow the repository's Conventional Commit history, such as `feat: add ...`,
`fix: validate ...`, `test: share ...`, and `docs: update ...`. Keep subjects
short and imperative. Pull requests should explain the behavioral change, link
relevant issues, note registry or specification effects, and include tests.
Before requesting review, run `devenv test` and report any intentionally skipped
live-source checks.
