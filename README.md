# Datamonger

Datamonger is a cross-language registry and artifact system for retrieving,
verifying, and identically decoding public research datasets.

The vertical proof, the specification-and-registry milestone, and the Python
retrieval and decoding milestones are complete. Normative draft contracts live in
[`spec/`](spec/); see [DESIGN.md](DESIGN.md) for the architecture and
[TODO.md](TODO.md) for the implementation roadmap.

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

### Manifest authoring

`dm-add` completes a partial manifest with facts derived from the artifacts and
the reference decoder:

```console
cd packages/python
uv run python ../../tools/dm_add.py path/to/draft.yaml
uv run python ../../tools/dm_add.py path/to/draft.yaml \
  --output ../../registry/datasets/uci/example-1.yaml
```

The draft supplies the dataset identity, descriptive and license metadata,
artifact names, formats, explicit compression, download locations, decoder
recipe, and any tasks. It may omit `provenance.retrieved_at`, artifact `size`
and `sha256`, and `representation.expect`; `dm-add` derives those fields. If a
derived field is already present, it must match exactly.

Every declared location is downloaded and must produce identical bytes after
HTTP content coding is removed. File-level compression must match the explicit
declaration. The completed YAML is written to stdout by default, while artifact
facts, decoded shapes, and bounded representative values are written to stderr.
Use `--output` to write a new file and add `--force` only for an intentional
replacement. Output YAML does not preserve comments or layout from the draft.

The candidate canonical digest is an authoring aid, not an independent
attestation. Stable publication still requires reproduction by another
implementation and human review of shapes, names, and representative values.

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

The immutable releases under `tests/registry` contain tiny CSV, TSV, LIBSVM,
SVMLight, and split-assembly datasets. Their generated indexes and the
language-neutral cases under `tests/conformance` are the shared source of
golden bytes, malformed inputs, properties, and fuzz regressions for the future
R and Julia clients.
