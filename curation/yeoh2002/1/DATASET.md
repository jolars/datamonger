# Gene expression and pediatric acute lymphoblastic leukemia subtype

This dataset contains gene expression measurements for 248 diagnostic bone
marrow samples from children with acute lymphoblastic leukemia (ALL). Yeoh and
colleagues used Affymetrix HG-U95Av2 microarrays to study whether gene
expression could identify ALL subtypes. Each sample has measurements for 12,625
probe sets.

## Data layout

`data.csv.gz` is a gzip-compressed UTF-8 CSV with a header. It has 248 rows and
12,627 columns. The first column, `sample_id`, gives the source sample
identifier. It serves as metadata and often contains the subtype name. Use the
next 12,625 columns, named by their probe-set IDs, as predictors. The last
column, `subtype`, is the classification target.

  | Label      | Subtype                                    | Samples |
  | ---------- | ------------------------------------------ | ------: |
  | `BCR`      | BCR-ABL                                    |      15 |
  | `E2A`      | E2A-PBX1                                   |      27 |
  | `Hyperdip` | Hyperdiploid with more than 50 chromosomes |      64 |
  | `MLL`      | MLL rearrangement                          |      20 |
  | `T`        | T-lineage ALL                              |      43 |
  | `TEL`      | TEL-AML1                                   |      79 |

All values are present. The source object supplies no training or test split for
this cohort.

## Preparation

Bioconductor's `stjudem` package processed the original arrays using
variance-stabilizing normalization at probe level and median polish to obtain
probe-set expression values. These values are on the package's normalized
expression scale.

The source expression matrix has 327 samples. This version keeps every sample
with one of the six labels in the table, preserving sample and probe-set order,
identifiers, and numeric precision. The resulting measurements and labels match
Iowa Biostatistics' measured Yeoh2002 cohort exactly. The dataset contains the
source measurements and labels without Iowa's simulated prediction set or added
feature annotations. No further normalization or imputation is applied.

## Files

- `data.csv.gz` contains the measured cohort.
- `stjudem_1.16.0.tar.gz` is the original Bioconductor data package, including
  the source R data object and its documentation.
- `convert.R` extracts the selected cohort from the source object and writes a
  CSV with 17 significant digits for each measurement.
- `provenance.json` records the source and output digests, conversion
  environment, and canonical verification. Each decoded measurement was checked
  against the source binary64 value.
- `README.md` is this documentation.
- `COPYING.LIB` contains the LGPL version 2 text, and `LICENSE` covers the new
  script and documentation under MIT.

To reproduce the uncompressed CSV, extract `stjudem/data/stjude.rda` from the
source archive and run the following command from the directory containing the
extracted files and the script. The last argument receives the measurement bits
used for validation.

```console
LC_ALL=C Rscript --vanilla convert.R stjudem/data/stjude.rda data.csv values.bin
```

## Citation and reuse

Cite Yeoh EJ et al. (2002), *Classification, subtype discovery, and prediction
of outcome in pediatric acute lymphoblastic leukemia by gene expression
profiling*. Cancer Cell 1(2), 133–143. Also credit Benjamin Georgi, Matthias
Heinig, Sebastian Schmeier, and Joern Toedling for the processed `stjudem` data.
[Study DOI](https://doi.org/10.1016/S1535-6108(02)00032-6), [Bioconductor
package DOI](https://doi.org/10.18129/B9.bioc.stjudem).

The source package declares LGPL version 2 or later. The portable data retain
that license and the source package's attribution. [Bioconductor 3.5 package
record](https://mirrors.nju.edu.cn/bioconductor/packages/3.5/data/experiment/html/stjudem.html),
[LGPL-2.0-or-later](https://spdx.org/licenses/LGPL-2.0-or-later.html).
