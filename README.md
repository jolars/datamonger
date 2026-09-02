# Datamonger

Datamonger is a cross-language registry and artifact system for retrieving,
verifying, and identically decoding public research datasets.

The vertical proof and the first specification-and-registry milestone are
complete. Normative draft contracts live in [`spec/`](spec/); see
[DESIGN.md](DESIGN.md) for the architecture and [TODO.md](TODO.md) for the
implementation roadmap.

## Development

Enter the devenv shell, then run the quality gate:

```console
devenv test
```

The Python reference client lives in `packages/python`.

Registry authors can validate deterministic generated files with:

```console
cd packages/python
uv run python ../../tools/dm_index.py check
```

For production releases, the command also checks the generated HTTPS release
catalog at `registry/catalog.json`. Building a production release refreshes the
catalog after writing its immutable index and selector.

## Vertical-proof registry

The legacy prerelease `proof-0001` registry contains UCI Iris and LIBSVM
`heart_scale`. Its strong selector is checked in at
`registry/releases/proof-0001/selector.json`; the selected index is published as
the sole asset of the `registry-proof-0001` GitHub prerelease. The Python client
also ships the exact index and its trusted digest as its default registry.
Dataset artifacts remain upstream-only.

The scheduled live-source workflow fetches both datasets through that remote
index. It is deliberately separate from the hermetic quality gate because
upstream drift and availability are operational signals, not package-test
failures.

## Conformance registry

The immutable `test-0001` release under `tests/registry` contains tiny CSV, TSV,
and LIBSVM artifacts. Its generated index and language-neutral cases under
`tests/conformance` are the shared source of golden bytes, malformed inputs,
properties, and fuzz regressions for the future R and Julia clients.
