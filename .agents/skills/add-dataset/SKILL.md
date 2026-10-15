---
name: add-dataset
description: Add a dataset or a new dataset version to Datamonger's registry, including source review, manifest authoring, collection registration, and validation. Use for registry additions, not client fetch usage or registry publication.
---

# Add a Datamonger Dataset

Produce a reviewed manifest under `registry/datasets/<source>/<name>-<version>.yaml`
and select it in `registry/collection.yaml` for the next registry release.
Run commands from the repository root in its devenv shell.

Read [the dataset contribution workflow](../../../CONTRIBUTING.md#adding-or-revising-a-dataset),
[the manifest schema](../../../spec/schema/manifest-v1.schema.json), and
[the identity contract](../../../spec/identity.md). These own the requirements;
use existing manifests as examples rather than copying their claims or digests.

## Establish the source and identity

- Inspect the provider's landing page and actual download locations. Verify
  upstream identity, authorship, citation, license evidence, and any documented
  preprocessing or train/test split. Ask for clarification only when the
  requested dataset or variant cannot be identified from the available evidence.
- Search existing manifests and published indexes before choosing
  `(source, name, version)`. Quote YAML versions as strings. Artifact bytes,
  artifact format or compression, and the complete representation recipe are
  immutable for a published identity; changes require a new dataset version.
- Use `license.status: unknown` when evidence is insufficient. Public download
  access does not establish a license, and a provider's software license may
  not cover its datasets. Record useful evidence without inventing reviewer
  identities or attestations.
- Use `upstream-only` for upstream downloads. Claim a mirror or durable
  preservation only with the evidence and review required by
  [TRUST.md](../../../TRUST.md#distribution-preservation-and-upstream-risk).

## Draft a supported representation

Keep drafts and downloaded artifacts in temporary storage outside the working
tree. Never commit upstream dataset artifacts.

Choose an existing version 1 decoder and read its contract:

- [Delimited text](../../../spec/decoders/delimited-text-v1.md): CSV or TSV with
  a UTF-8 header that exactly matches the declared, ordered columns. Declare
  logical types and missing tokens explicitly. The decoder does not infer
  types, trim fields, or accept arbitrary separators.
- [LIBSVM](../../../spec/decoders/libsvm-v1.md): use `libsvm` for one artifact or
  `libsvm-split` for predefined train/test artifacts. Derive `feature_count`
  from the documented feature space and inspect both splits. Preserve splits
  and the provider's representation, including any scaling already applied.

Useful examples are `registry/datasets/uci/iris-1.yaml`,
`registry/datasets/libsvm/heart_scale-1.yaml`, and
`registry/datasets/libsvm/dna_scale-1.yaml`.

If the available artifact cannot satisfy an existing decoder, explain the
specific incompatibility and look for an official supported representation.
Do not silently clean, convert, or rehost data, or extend a frozen contract to
make an ordinary registry addition pass.

Supply identity, descriptive metadata, provenance, license, artifacts and their
download locations, representation inputs and options, and appropriate tasks.
For a new draft, omit artifact `size` and `sha256`, `representation.expect`,
and an unknown `provenance.retrieved_at`; let `dm-add` derive them. Do not copy
these values from another dataset.

Declare feature and target roles deliberately. Exclude IDs and bookkeeping
columns from model features when appropriate, retain them in the decoded data,
and distinguish classification labels from regression responses. Use named
task splits for a split representation.

## Complete and review the manifest

Replace the paths below with the actual draft and new manifest paths:

```console
uv run --project packages/python python tools/dm_add.py /tmp/draft.yaml \
  --output registry/datasets/<source>/<name>-<version>.yaml
```

`dm-add` fetches every location, requires identical artifact bytes, checks
compression, decodes the representation, and derives sizes, SHA-256 digests,
component expectations, and canonical verification. It validates the completed
manifest and prints a bounded review report to stderr. Existing derived fields
are checked, so retain them when rechecking a completed manifest.

Review the report against the provider's documentation: row and feature counts,
column names and types, missing values, labels, splits, and representative
values. Investigate disagreements. Generated verification is an authoring aid,
not an independent attestation. Use `--force` only for an intentional replacement
of an unpublished output. If retrieval or decoding fails, report the actual
failure and do not manufacture hashes or expectations.

## Register and validate

Add the manifest path to `registry/collection.yaml`. For a new dataset, add its
`source`, `name`, and quoted `version` to `defaults`. For an additional version,
make the default choice explicit and preserve existing versions. Follow the
surrounding ordering and formatting.

The normal index check validates existing release snapshots; it does not
validate newly selected collection entries. Check the updated collection in a
temporary copy, with a sequence after every historical release, so `dm-index`
also enforces identity and append-only evolution rules:

```bash
uv run --project packages/python python - <<'PY'
from pathlib import Path
import shutil
import sys
import tempfile

import yaml

root = Path.cwd()
sys.path.insert(0, str(root / "tools"))
import dm_index

with tempfile.TemporaryDirectory(prefix="dm-collection-check-") as directory:
    staging = Path(directory)
    for relative in ("registry", "spec/schema"):
        shutil.copytree(root / relative, staging / relative)
    releases = staging / "registry/releases"
    sequence = max(
        dm_index.load_yaml(path)["sequence"]
        for path in releases.glob("*/release.yaml")
    ) + 1
    source = dict(dm_index.load_yaml(staging / "registry/collection.yaml"))
    source.update(release="local-check", sequence=sequence, tag="local-check")
    path = releases / "local-check/release.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    dm_index.build(path, root=staging)
print("Collection validation passed.")
PY
```

Run `devenv test`. Keep any new regression tests deterministic and offline;
network-dependent tests belong in the affected client's `tests_live` directory.
Published-registry audits do not exercise an unpublished addition.

Leave release snapshots, indexes, selectors, catalogs, registry version bumps,
and bundled client registries to the Versionary release workflow in
[OPERATIONS.md](../../../OPERATIONS.md#prepare-a-registry-release). Adding a
dataset does not authorize publishing a registry. Release approval requires
the independent verification described there.

Report the canonical dataset ID, files changed, source and license evidence,
decoded dimensions and task roles, validation results, and any unresolved
limitations or skipped live checks. If committing, use `feat(registry): ...`
for an addition.
