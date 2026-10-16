# BRCA1 expression in TCGA breast cancer samples

Version: 1. Datamonger representation: `datamonger:brca1@1`.
DOI: [10.5281/zenodo.23418110](https://doi.org/10.5281/zenodo.23418110).

This dataset contains Agilent gene expression measurements for 536 TCGA breast
cancer samples: 533 primary tumors and three metastatic tumors. BRCA1 expression
is a continuous response for regression on the expression of other genes.
Datamonger prepares this representation directly from the official TCGA Level 3
archive hosted by the NCI Genomic Data Commons (GDC).

## Data

`data.csv.gz` decompresses to a UTF-8 CSV with a header, 536 rows, and 17,324
columns:

- `sample_id`: the public TCGA aliquot barcode, retained as metadata.
- The next 17,322 columns: gene expression predictors, named with the official
  gene symbols and ordered lexicographically.
- `y`: BRCA1 expression, excluded from the predictors.

The source specifies log2 lowess-normalized Cy5/Cy3 ratios, collapsed by gene
symbol. This conversion applies no additional logarithm, scaling, centering,
or imputation. All numeric values retain the binary64 precision obtained from
the official text. There are no missing values in the sample table and no
predefined training or test split. Samples are ordered by their TCGA barcodes.
The sample identifier is excluded from model features.

## Source and preparation

The source is [BRCA.Gene_Expression.Level_3.tar](https://api.gdc.cancer.gov/data/f0b74706-6b9e-4430-931d-9f233b4ac67c),
linked from the [GDC publication page](https://gdc.cancer.gov/about-data/publications/brca_2012)
for *Comprehensive molecular portraits of human breast tumors*.
The archive is 78,264,320 bytes, with SHA-256:

```text
e49acb5b765d9ada53a713cb95d0a34bcdb60836a1eff2a44d4f0414f4c24af1
```

The published MD5 is `e18990520aef7e2d3a7b8e301f040538`.

The underlying archive contains samples beyond the publication's centered
547-sample matrix. Preparation reads the original Level 3 measurements,
consolidates one duplicate sample, and selects primary and metastatic tumor
sample types `01` and `06`. The duplicate
`TCGA-AN-A0AL-01A-11R-A00Z-07` appears in two batches with identical measurement
records; the earlier header has an extra trailing space. Extraction verifies
the duplicate records and keeps the copy with the corrected identifier.
There are 606 unique samples, of which 63 normal samples and seven control
samples are excluded. Of 17,814 measured genes, 491 have missing measurements
in the selected tumor cohort and are excluded. BRCA1 becomes the response;
the other 17,322 complete genes become predictors.

The cohort matches Iowa Biostatistics'
[`brca1` dataset](https://iowabiostat.github.io/data-sets/brca1/brca1.html).
The largest absolute difference across matched numeric measurements is about
`4.55e-8`; these files preserve the official precision. The official symbol
`SEP15` corresponds to Iowa's `SEPT15`. The output also retains TCGA sample
IDs, which Iowa's RDS omits. Iowa's additional chromosome and gene-name
annotations are not included.

## Files and verification

The portable file set consists of:

- `data.csv.gz`: the sample table.
- `read_source.R`: preparation from the extracted official sample files.
- `convert.R`: CSV serialization with 17 significant digits.
- `verify.R`: the complete R round trip and comparison of the source canonical
  digest with the Python decoder's digest.
- `prepare.py`: source retrieval, extraction, deterministic gzip compression,
  manifest preparation, and validation in the Datamonger environment.
- `provenance.json`: source, artifact, environment, and verification details.
- `LICENSE`: the MIT license for the preparation scripts and documentation.
- `README.md`: this document.

Gzip compression uses level 9 with no original filename or timestamp.
The R source preparation and Python CSV decoder produce identical canonical
digests. The scripts require the
[Datamonger repository](https://github.com/jolars/datamonger) and its Python and
R clients. In a checkout without this curation directory, place the four attached
scripts in `curation/brca1/1/` and save this README there as `DATASET.md`.
Run the preparation in the repository's devenv shell:

```console
uv run --project packages/python python curation/brca1/1/prepare.py /tmp/brca1-reproduction
```

The original archive and extracted sample files are retrieved during preparation
and are outside this portable file set.

## Citation and rights

Use the version-specific DOI above to cite this portable representation. The
original TCGA reference is:

The Cancer Genome Atlas Network (2012). Comprehensive molecular portraits of
human breast tumours. *Nature* 490:61–70.
[doi:10.1038/nature11412](https://doi.org/10.1038/nature11412).

Credit the [TCGA Research Network](https://www.cancer.gov/tcga), the University
of North Carolina Cancer Genomic Characterization Center that produced the
measurements, and the NCI GDC source. Credit Iowa Biostatistics for the reference
BRCA1 regression dataset and Datamonger for this portable representation.

The data are published under the source terms in the
[GDC Data Analysis Policies](https://gdc.cancer.gov/analyze-data/data-analysis-policies)
and [GDC Data Access Policies](https://gdc.cancer.gov/access-data/data-access-policies).
Retain source attribution and the prohibition on attempts to reidentify
participants. These source policies permit publication of open-access data;
no standard data license or public-domain dedication is asserted.

The preparation scripts and this documentation use the MIT license in
`LICENSE`. That software and documentation license does not apply to the TCGA
measurements.
