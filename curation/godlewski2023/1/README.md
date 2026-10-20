# Preparing the Godlewski2023 metabolomics table

The intended identity is `datamonger:godlewski2023@1`. Preparation uses the original
Supplementary Table S2 from Godlewski et al. (2023), not SLOPE's binary example.
`DATASET.md` is the public documentation, uploaded as `README.md`.
`RIGHTS.md` records the CC BY 4.0 source review.

## Reproduce and validate

Run from the repository root in its devenv shell, using new output directories
outside the working tree:

```console
uv run --project packages/python python curation/godlewski2023/1/prepare.py /tmp/godlewski2023-reproduction
uv run --script curation/godlewski2023/1/verify.py /tmp/godlewski2023-reproduction/sources/41598_2023_38243_MOESM2_ESM.xlsx /tmp/godlewski2023-reproduction/data.csv.gz
env -u LD_LIBRARY_PATH Rscript curation/godlewski2023/1/verify.R "$PWD" /tmp/godlewski2023-reproduction
```

`prepare.py` pins the source size and SHA-256, copies the source's numeric XML
tokens exactly into CSV fields, and uses deterministic gzip compression.
The script retains all 235 rows and 140 columns, checks the identifiers and
six label counts, decodes the result, and writes `manifest.local.yaml` and
`provenance.json`. The local manifest is `metadata-only` without download
locations and must not be selected in the production collection.

To reuse a downloaded workbook, pass `--source /path/to/source.xlsx`.
To check repeatability, run again into a different directory and compare the
`data.csv.gz` hashes. `verify.py` uses openpyxl independently of the XML reader
to compare every header and value. `verify.R` compares the R and Python
canonical digests. These are conversion checks, not the independent release
review required by `OPERATIONS.md`.

The R command clears Python's manylinux library path so Nix's R helpers use
their own libraries.

## Deposit and register

The seven public files are listed in `DATASET.md`. Upload only those files;
keep this maintainer README, rights assessment, source workbook, and local
manifest outside the deposit. Record the original authors as creators, the
paper DOI as the source, version 1, open file access, and CC BY 4.0 for the
data. Distinguish the preparation code's MIT license in the public description.

Public publication and registration were authorized by the user on
October 20, 2026. Resume any existing deposit from `zenodo-record.json` instead
of creating a duplicate. Record its ID promptly. After publication, verify
the DOI, rights, record and file access, and anonymously downloaded hashes
for all seven files.

Only then author `registry/datasets/datamonger/godlewski2023-1.yaml` with `dm-add`
against the public, version-specific CSV URL, record the preservation review,
and select the manifest and default in `registry/collection.yaml`. Validate
the updated collection in a temporary release after historical sequences.
Dataset publication does not authorize a registry release.
