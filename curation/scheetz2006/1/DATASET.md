# Gene expression in the mammalian eye

This dataset contains processed gene expression measurements from the eyes of
120 male F2 rats from an SR/JrHsd × SHRSP intercross. Scheetz and colleagues
collected these data to investigate gene regulation and its relevance to eye
disease. The regression response is expression of Trim32, also called Bbs11,
measured by probe `1389163_at`. The predictors measure expression of 18,985
other probes. Probes are measurement features, not necessarily distinct genes.

The measurements come directly from the authors' [GEO submission,
GSE5680](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE5680).
The preparation applies the paper's filter to GEO's full-precision values and
retains GEO's sample identifiers. It includes 10 more predictors than
[Iowa Biostatistics' Scheetz2006 dataset](https://iowabiostat.github.io/data-sets/Scheetz2006/Scheetz2006.html).
Iowa's RDS, code, and gene annotations are not preparation inputs.

## Data layout

`data.csv.gz` is a UTF-8 CSV with a header, compressed with gzip. It has 120
rows and 18,987 columns:

- `sample_id`: the public GEO sample accession, retained as metadata and
  excluded from model features.
- 18,985 predictor columns named by Affymetrix probe identifiers, in GEO's
  probe order.
- `y`: the numeric expression measurement for Trim32 probe `1389163_at`.

Rows follow the sample order in GEO's series matrix. This differs from Iowa's
row order. There is no predefined training or test split. Every measurement
is present, and no missing tokens or imputation are used.

GEO describes the measurements as summary expression values produced with
RMA (robust multi-chip averaging). These are expression values on a log2
scale, not raw fluorescence intensities or counts. Preparation does not rerun
RMA, standardize predictors, or apply another logarithm.

## Preparation and relationship to Iowa's version

The source series matrix contains 31,099 probes across 120 samples. Preparation
excludes 57 `AFFX` control probes, leaving the 31,042 noncontrol probes discussed
in the paper. The paper selects probes whose maximum expression exceeds the
global first quartile and whose expression varies by at least twofold.

Preparation calculates the global first quartile of all noncontrol expression
values using R's type 7 quantile (`4.2818075363880554` for the pinned source).
It keeps a probe if its maximum exceeds this
threshold and its maximum minus minimum is at least one on the log2 scale.
A one-unit difference on that scale corresponds to a twofold expression change.
No values are rounded for selection or output. The selected matrix is
transposed so samples are rows, and `1389163_at` becomes `y`.

This retains 18,986 probes, including Trim32, rather than the paper's reported
18,976. All probes in Iowa's version are present, plus 10 additional predictors
at the filtering boundaries. Iowa's public script reads an already filtered
local text file and does not document its filtering. Applying a filter to
three-decimal values can reproduce its smaller probe set. This version uses
the paper's rule at GEO precision and does not infer the unpublished original
filtering implementation.

The additional predictors are `1368142_at`, `1371411_at`, `1373846_at`,
`1375032_at`, `1375448_at`, `1377049_at`, `1385573_at`, `1387136_at`,
`1392632_at`, and `1397254_at`.

The measurements shared with Iowa agree within `0.0005` after matching samples
and probes. This output preserves GEO's precision and order and includes the
additional probes, so it differs logically from Iowa's rounded export.
The added `fData` gene symbols, descriptions, and chromosome annotations in
Iowa's RDS are omitted. Probe identifiers remain in the column names.

## Included files and verification

- `data.csv.gz`: the portable numeric dataset and sample identifiers.
- `README.md`: this dataset documentation.
- `prepare.py`, `read_source.R`, `convert.R`, and `verify.R`: acquisition,
  preparation, and verification scripts.
- `provenance.json`: source and output hashes, environment, dimensions, and
  canonical verification.
- `LICENSE`: the MIT license for the preparation code and documentation.

The scripts require the Datamonger repository and its devenv environment.
Run `prepare.py` from `curation/scheetz2006/1/` in that repository, passing a new
output directory outside the working tree. It verifies the pinned source size
and SHA-256, then prepares the CSV using 17 significant digits for numeric
round trips. R checks exact agreement with the prepared source values. The
R and Python canonical digests must agree, including sample IDs, probe names,
order, types, and values. These checks validate the conversion; they are not
an independent registry release attestation.

## Citation and reuse terms

Scheetz TE, Kim K-YA, Swiderski RE, Philp AR, Braun TA, Knudtson KL,
Dorrance AM, DiBona GF, Huang J, Casavant TL, Sheffield VC, and Stone EM (2006).
Regulation of gene expression in the mammalian eye and its relevance to eye
disease. *Proceedings of the National Academy of Sciences* 103:14429–14434.
[doi:10.1073/pnas.0602562103](https://doi.org/10.1073/pnas.0602562103).
GEO accession: GSE5680.

Credit the study authors and GEO for the source data and Datamonger for this
portable preparation. Iowa Biostatistics provides the comparison reference.

The [GEO disclaimer](https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html)
places no restrictions on use or distribution of GEO data, while warning that
submitters may retain intellectual property rights. The automated review found
no additional data-specific restriction in the reviewed GSE5680 records. These
source terms supply the redistribution basis recorded here; they do not
establish a named SPDX license or a public-domain dedication. The repository's
MIT license applies to preparation code and documentation, not the underlying
measurements.
