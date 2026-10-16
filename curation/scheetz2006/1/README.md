# Preparing Scheetz2006 from the original source

The dataset is `datamonger:scheetz2006@1`, published on
[Zenodo](https://doi.org/10.5281/zenodo.23420731) with public record and file
access. Its measurements come from the authors' GSE5680 submission to NCBI
GEO. The recipe applies the paper's filter at full precision while preserving
GEO's sample identifiers and sample and probe order. `DATASET.md` explains the
filter and its 10 additional predictors relative to Iowa's rounded export.
`RIGHTS.md` records the source-policy review, and `zenodo-record.json` records
publication and download verification.

## Reproduce and validate

Run from the repository root in its devenv shell:

```console
uv run --project packages/python python curation/scheetz2006/1/prepare.py /tmp/scheetz2006-reproduction
```

To reuse the pinned source, add
`--source /path/to/GSE5680_series_matrix.txt.gz`. Both paths verify its
29,409,846-byte size and SHA-256:
`ff7c8926a30267df8b08d1d1f37b710e81f2e3b115341a4a445b0c02da88edb5`. The source
URL is recorded in `prepare.py`. GEO may regenerate compressed exports, so a
later source mismatch requires review, not bypassing the pin.

The command prepares a CSV with 120 rows and 18,987 columns: `sample_id`, 18,985
predictors, and regression response `y` (Trim32). The identifier is excluded
from model features. R checks every value against the prepared GEO source, and
the R and Python canonical digests must agree. This is conversion validation,
not independent release attestation. Run the preparation twice and compare
`data.csv.gz` hashes to check repeatability.

The recipe pins the compressed artifact, uncompressed CSV, and canonical form 1
digests alongside the source hash. `provenance.json` records them. The
compressed artifact is 19,425,274 bytes with SHA-256
`8348d10e5ef29b95c5a9a757e0cee189758364bfae22baef72027a041cf0156e`. Its
canonical form 1 SHA-256 is
`efcb6e82af27379e0959e5722b2e35a2db08a31a104d329c05da7430c2263b19`.

Generated files, source downloads, and `manifest.local.yaml` stay outside the
repository. The local manifest uses `metadata-only` with no download locations.

## Optional comparison with Iowa

Iowa's reference is pinned to commit `f6b782b919a76898dbc1f0421e96274ef6987b6d`.
Its actual RDS content is available from:

```text
https://media.githubusercontent.com/media/IowaBiostat/data-sets/f6b782b919a76898dbc1f0421e96274ef6987b6d/Scheetz2006/Scheetz2006.rds
```

Its SHA-256 is
`1b3450f6ed59afce27dd162e4563aa27c6512e41f65735b5fa448e0643d5d6b4`. After
verifying that digest, compare the two sources with:

```console
Rscript curation/scheetz2006/1/compare_reference.R /path/to/GSE5680_series_matrix.txt.gz /path/to/Scheetz2006.rds curation/scheetz2006/1/read_source.R
```

The comparison checks that Iowa's probe set is contained in this version,
uniquely matches all 120 samples using several probes, and bounds the difference
across every shared predictor and response value by `0.000501`. Iowa's sample
and probe order differ from GEO's. The comparison script and Iowa artifact are
not needed to reproduce the output.

## Deposit and registration

The deposit contains the eight files listed in `DATASET.md`, which is uploaded
as `README.md`. This maintainer README, the detailed rights review, optional
comparison script, source matrix, and local manifest stay outside the deposit.
The custom data rights statement records GEO's source terms and their
qualifications. The separate MIT license covers the scripts and documentation.

The production manifest is `registry/datasets/datamonger/scheetz2006-1.yaml`.
It uses the verified public, version-specific Zenodo artifact URL and records
the deposit review. Recheck that manifest with `dm-add` when auditing
availability. `registry/collection.yaml` selects the dataset for the next
registry release. Dataset publication does not publish a registry release;
apply the separate independent release review before releasing the registry.
