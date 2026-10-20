# Preparing the Godlewski2023 metabolomics table

The dataset identity is `datamonger:godlewski2023@1`. Preparation uses the original
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

## Published deposit and registry entry

Version 1 was published on October 20, 2026, at
[Zenodo](https://doi.org/10.5281/zenodo.23498714), following the user's
authorization. `zenodo-record.json` records publication, open record and file
access, rights, and SHA-256 verification of anonymous downloads of all seven
files listed in `DATASET.md`. The record credits the original authors as
creators and Datamonger as data curator. Its description and public README
scope CC BY 4.0 to the data and MIT to preparation code and documentation.
This maintainer README, rights assessment, source workbook, and local
manifest are not deposited.

`registry/datasets/datamonger/godlewski2023-1.yaml` uses the public,
version-specific CSV URL and records the preservation review. Recheck it
with `dm-add` when auditing the deposit. The manifest and default are selected
in `registry/collection.yaml`; validate collection changes in a temporary
release after historical sequences. A registry release still requires the
independent review and publication workflow in `OPERATIONS.md`.
