# Preparing the BRCA1 dataset

The dataset is `datamonger:brca1@1`, prepared from the official TCGA Level 3
archive hosted by the NCI Genomic Data Commons (GDC). Version 1 is published on
[Zenodo](https://doi.org/10.5281/zenodo.23418110), with public record and file
access. [zenodo-record.json](zenodo-record.json) records publication and download
verification. [RIGHTS.md](RIGHTS.md) records the GDC source terms and the
automated review.

## Reproduce and validate

Run in the repository's devenv shell with a new directory outside the repo:

```console
uv run --project packages/python python curation/brca1/1/prepare.py /tmp/brca1-reproduction
```

To reuse the pinned source archive, add
`--source /path/to/BRCA.Gene_Expression.Level_3.tar`. Both acquisition paths
check its size and SHA-256.

The workflow reads the nested TCGA archives, consolidates one duplicate with
identical measurements, and selects primary and metastatic tumors. It preserves
the official numeric precision and sample identifiers. The resulting CSV has 536
rows and 17,324 columns: `sample_id`, 17,322 gene expression predictors, and the
regression response `y`. `sample_id` is excluded from model features. The sample
and gene orders are explicit and reproducible.

`read_source.R` prepares the source values independently of CSV decoding.
`convert.R` serializes them, the Python client decodes the complete compressed
CSV, and `verify.R` checks the full R round trip and source canonical digest.
Generated data, extracted sample files, and the local manifest stay outside the
repository. This is conversion validation, not an independent release
attestation.

## Relationship to Iowa's dataset

The [official Level 3
archive](https://api.gdc.cancer.gov/data/f0b74706-6b9e-4430-931d-9f233b4ac67c)
is linked from the [GDC publication
page](https://gdc.cancer.gov/about-data/publications/brca_2012). It contains all
536 samples represented by Iowa's
[`brca1`](https://github.com/IowaBiostat/data-sets/tree/f6b782b919a76898dbc1f0421e96274ef6987b6d/brca1).
Their sample order matches sorted TCGA barcodes. Across the matched numeric
measurements, the maximum absolute difference from Iowa's RDS is approximately
`4.55e-8`. The official gene symbol `SEP15` corresponds to Iowa's `SEPT15`. The
output preserves official symbols and precision and retains sample IDs. Iowa's
RDS and its added `fData` annotations are not preparation inputs.

The archive's 607 files describe 606 unique samples. The two copies of
`TCGA-AN-A0AL-01A-11R-A00Z-07` have identical measurement records; one has a
trailing space in its header identifier. Extraction checks their equality and
keeps the copy with the corrected identifier. Selecting TCGA sample types `01`
and `06` yields 533 primary tumors and three metastatic tumors. The 63 normal
samples and seven control samples are excluded.

## Deposit and registry maintenance

The deposit contains the portable file set listed in `DATASET.md`, uploaded as
its `README.md`. The maintainer instructions and detailed `RIGHTS.md` review stay
in Git. The deposit also includes the repository's `LICENSE` for its scripts
and documentation. Its custom data rights statement retains attribution and
the prohibition on reidentification. Do not substitute an unsupported SPDX
license or public-domain claim. The automated source review does not assert a
human maintainer's legal review.

The generated `manifest.local.yaml` has `metadata-only` distribution and no
download locations. The production manifest is
`registry/datasets/datamonger/brca1-1.yaml`; it uses the verified public,
version-specific Zenodo artifact URL and records the deposit review. Recheck
that manifest with `dm-add` when auditing availability. Collection registration
selects the dataset for the next registry release; apply the separate,
independent release review before publishing that registry.
