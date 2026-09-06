# Datamonger

Datamonger is a cross-language registry and artifact system for retrieving,
verifying, and identically decoding public research datasets.

The vertical proof, the specification-and-registry milestone, the Python
retrieval and decoding milestones, the tooling-and-candidate-data milestone,
and the revision 1 feature freeze are complete. Normative versioned contracts
live in [`spec/`](spec/); see
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

### Upstream canary

`dm-canary` re-fetches a published registry index and every download location
without consulting the artifact cache, checks the registered sizes and SHA-256
digests, and decodes one verified copy of every dataset with the Python
reference client. Decoded components and a supported canonical digest must
still match the immutable registry record.

```console
cd packages/python
uv run python ../../tools/dm_canary.py \
  ../../registry/releases/candidate-0001/selector.json
```

The Markdown report exits with status 0 when every check passes, status 1 when
the remote index, a location, or decoded data has drifted, and status 2 when the
command or local selector is invalid. Location failures are aggregated, so a
bad location does not hide the status of later locations or other datasets.

The upstream-verification workflow runs every Monday at 06:00 UTC and can also
be dispatched manually. Its implementation matrix currently contains the
Python reference client; each released client must be added to that matrix so
every selected dataset and client combination runs weekly. A failed run opens
or updates an implementation-specific GitHub issue with the complete report;
the next successful run closes it. Canary results describe current
availability and integrity, not preservation.

## Candidate registry

The prerelease `candidate-0001` registry contains all ten reviewed UCI and
LIBSVM candidate datasets. Its strong selector is checked in at
`registry/releases/candidate-0001/selector.json`; the selected index is
published as the sole asset of the `registry-candidate-0001` GitHub prerelease.
The verification records remain provisional until an independent
implementation reproduces them, and no stable registry includes these records.

The scheduled upstream-verification workflow checks every candidate artifact
location and decoded dataset through the remote index. This is deliberately
separate from the hermetic quality gate because upstream drift and availability
are operational signals, not package-test failures.

## Vertical-proof registry

The legacy prerelease `proof-0001` registry contains UCI Iris and LIBSVM
`heart_scale`. Its strong selector is checked in at
`registry/releases/proof-0001/selector.json`; the selected index is published as
the sole asset of the `registry-proof-0001` GitHub prerelease. Dataset artifacts
remain upstream-only.

The Python client continues to bundle this exact legacy index and trusted digest
as its offline default. Selecting the newer candidate registry remains explicit
while the draft contracts are not independently certified.

## Conformance registry

The immutable releases under `tests/registry` contain tiny CSV, TSV, LIBSVM,
SVMLight, and split-assembly datasets. Their generated indexes and the
language-neutral cases under `tests/conformance` are the shared source of
golden bytes, malformed inputs, properties, and fuzz regressions for the future
R and Julia clients.
