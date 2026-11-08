# Maintaining the Rhee2006 dataset

The dataset is published at [doi:10.5281/zenodo.23398467](https://doi.org/10.5281/zenodo.23398467).
`DATASET.md` is the user-facing documentation deposited as `README.md`.
Keep maintainer workflow instructions in this file, outside the deposit.

The record was originally published with restricted files. On November 8,
2026, the user approved making the existing eight files public. The access
correction preserved the DOI, file bytes, and descriptive and rights metadata.
All eight files were downloaded anonymously and matched their original SHA-256
digests. `zenodo-record.json` retains the original hashes and records the access
correction and public download verification.

## Reproduce and validate

Run in the repository's devenv shell with a new directory outside the repo:

```console
uv run --project packages/python python curation/rhee2006/1/prepare.py /tmp/rhee2006-reproduction
```

The command downloads Stanford's original text file, verifies its pinned size
and SHA-256, prepares the mutation indicators and log susceptibility response,
and writes the reviewed CSV bytes. R verifies the numeric round trip. The R
and Python clients must agree with the canonical digest computed from the
prepared source values. This is conversion validation, not an independent
registry-release attestation.

Generated files stay outside the working tree. The local `manifest.local.yaml`
is an authoring artifact with no download locations, not a production manifest.
`PI_DATA.txt` is retained for local provenance and is not part of the deposit.
`RIGHTS.md` records the reviewed redistribution basis.

## Deposit and registry maintenance

Use the dataset README, preparation and verification scripts, provenance, and
rights statement in the deposit. Do not upload this maintainer README or the
local manifest. Keep metadata and documentation consistent with publication
status, and verify downloaded files after any upload.

For minor documentation corrections, follow Zenodo's published-file correction
workflow. Changes to data bytes or the representation require a new dataset
version. Keep the original publication DOI and the data hash in the publication
receipt.

The production manifest is `registry/datasets/datamonger/rhee2006-1.yaml`.
It selects the version-specific public Zenodo CSV and records the source rights
and preservation review. `registry/collection.yaml` selects
`datamonger:rhee2006@1` as the default for the next registry release.

Re-fetch and validate the production manifest with `dm-add` when auditing the
deposit. Dataset publication and collection registration do not publish a
registry release; follow the normal collection validation and independent
registry release workflow.
