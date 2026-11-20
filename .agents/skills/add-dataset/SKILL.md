---
name: add-dataset
description: Add or curate a Datamonger dataset, including source review, authorized conversion and dataset deposits, manifest authoring, collection registration, and validation. Not for client fetch usage or registry release publication.
---

# Add a Datamonger Dataset

Produce a reviewed manifest under `registry/datasets/<source>/<name>-<version>.yaml`
and select it in `registry/collection.yaml` for the next registry release.
For a conversion or deposit trial, complete the requested stage without adding
an unpublished or inaccessible artifact to the production collection.
Run commands from the repository root in its devenv shell.

Find the recommended manifest schema and check client compatibility notes in
the [dataset contribution workflow](../../../CONTRIBUTING.md#adding-or-revising-a-dataset).

## Establish the source and identity

- Inspect the provider's landing page and actual download locations. Verify
  upstream identity, authorship, citation, license evidence, and any documented
  preprocessing or train/test split. Ask for clarification only when the
  requested dataset or variant cannot be identified from the available evidence.
- Search existing manifests and published indexes before choosing
  `(source, name, version)`. Quote YAML versions as strings. Artifact bytes,
  artifact format or compression, and the complete representation recipe are
  immutable for a published identity. Changes require a new dataset version.
  See the [identity contract](../../../spec/identity.md).
- For new curated names under `datamonger`, follow the
  [curated dataset naming policy](../../../CONTRIBUTING.md#curated-dataset-names):
  use the first author's lowercase ASCII surname and publication year, letters
  starting with `b` for collisions between papers, and descriptive suffixes
  for distinct datasets within a paper. Check curation directories as well as
  registry records before allocating names. Keep existing IDs unchanged and
  reserve the separate version field for dataset versions.
- Use `license.status: unknown` when evidence is insufficient. Public download
  access does not establish a license, and a provider's software license may
  not cover its datasets. Record useful evidence without inventing reviewer
  identities or attestations. Source terms or a public-domain statement can
  establish a reviewed redistribution basis without a named SPDX license;
  record the evidence accurately rather than inferring a CC0 dedication.
- Use `upstream-only` for upstream downloads. Claim a mirror or durable
  preservation only with the evidence and review required by
  [TRUST.md](../../../TRUST.md#distribution-preservation-and-upstream-risk).

## Draft a supported representation

Keep drafts and downloaded or converted artifacts in temporary storage outside
the working tree. Commit recipes and documentation, not dataset artifacts.

Choose a `decoder` and `decoder_version` that fit the artifact format and
preserve the provider's split names and membership. Check that the manifest
schema allows the recipe and that `dm-add` supports it. Read the matching
contract in `spec/decoders/` and check for applicable extensions in the
[specification overview](../../../spec/README.md).

- For delimited text, match declared columns to the header in order. Declare
  logical types and missing tokens explicitly.
- For LIBSVM, derive `feature_count` from the documented feature space. Inspect
  every split and preserve any scaling already applied.

Look in `registry/datasets/` for structural examples using the selected schema
and decoder version.

If the available artifact cannot satisfy an existing decoder, explain the
specific incompatibility and look for an official supported representation.
Trace prepared collections back to their original sources before introducing
a decoder for a binary format such as RDS. If conversion or preservation is
within the user's scope, follow [curated representations and deposits](references/curated-deposits.md),
then return here to author the manifest against the deposited artifacts.
Do not silently clean, convert, or rehost data, or extend a frozen contract to
make an ordinary registry addition pass.

Supply identity, descriptive metadata, provenance, license, artifacts and their
download locations, representation inputs and options, and appropriate tasks.
Record upstream and Datamonger preparation separately using the
[preprocessing specification](../../../spec/preprocessing.md).

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

Under `datasets` in `registry/collection.yaml`, find or create the entry for the
dataset's source and name. Append the quoted version to its `versions` list,
preserving existing versions. The last version becomes the default.

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
    source, manifest_identities = dm_index.load_collection(staging)
    source.update(release="local-check", sequence=sequence, tag="local-check")
    path = releases / "local-check/release.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    dm_index.build(path, root=staging, manifest_identities=manifest_identities)
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
limitations or skipped live checks. For a deposit, include its URL, publication
and file-access status, and download verification. If committing, use `feat(registry): ...`
for an addition.
