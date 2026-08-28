# Datamonger

Datamonger is a cross-language registry and artifact system for retrieving,
verifying, and identically decoding public research datasets.

The project is in its vertical-proof phase. See [DESIGN.md](DESIGN.md) for the
architecture and [TODO.md](TODO.md) for the implementation roadmap.

## Development

Enter the devenv shell, then run the quality gate:

```console
devenv test
```

The Python reference client lives in `packages/python`.

## Vertical-proof registry

The provisional `proof-0001` registry contains UCI Iris and LIBSVM
`heart_scale`. Its strong selector is checked in at
`registry/releases/proof-0001/selector.json`; the selected index is published as
the sole asset of the `registry-proof-0001` GitHub prerelease. Dataset artifacts
remain upstream-only.

The scheduled live-source workflow fetches both datasets through that remote
index. It is deliberately separate from the hermetic quality gate because
upstream drift and availability are operational signals, not package-test
failures.
