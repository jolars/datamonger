# Gene expression and relative ovarian xenograft tumor volume

This dataset contains 101 ovarian cancer xenograft samples from the OV1002
and HOX424 models grown in mice. Koussounadis and colleagues measured gene
expression and tumor growth after carboplatin, carboplatin plus paclitaxel,
or no treatment. The regression response is log2 relative tumor volume (RTV).
The 34,694 predictors summarize processed Illumina expression measurements by
the platform's internal gene labels.

All preparation inputs come from NCBI GEO: the authors' [GSE49577
submission](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE49577), its
supplementary phenodata table, and the [GPL10558
platform](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GPL10558).
[Iowa Biostatistics' Koussounadis2014
dataset](https://github.com/IowaBiostat/data-sets/tree/f6b782b919a76898dbc1f0421e96274ef6987b6d/Koussounadis2014)
provides a comparison reference. Its RDS, code, and local phenodata copy are
not preparation inputs.

## Data layout

`data.csv.gz` is a UTF-8 CSV with a header, compressed with gzip. Its 101 rows
and 34,701 columns consist of:

- `sample_id`: the public GEO sample accession.
- `tumor_id`: the authors' sample identifier, such as `319L`.
- `Treatment`: `Carbo` (carboplatin), `CarboTax` (carboplatin and paclitaxel),
  or `Control` (untreated).
- `Day`: integer days after treatment, drawn from 0, 1, 2, 4, 7, and 14.
- `CellLine`: the ovarian cancer model, `OV1002` or `HOX424`.
- `RTV`: tumor volume divided by that tumor's baseline volume, retained at
  the submitted precision.
- 34,694 numeric predictor columns named by GPL10558's `ILMN_Gene` field.
- `y`: `log2(RTV)`, so zero indicates baseline size and one indicates a
  doubling of volume.

Rows follow GEO's series matrix sample order. Predictor labels use ASCII byte
order. The default regression task uses the 34,694 expression columns as
features and `y` as its target. The six metadata columns are excluded from
features; in particular, `RTV` determines the target directly. There is no
predefined training or test split. All values are present, with no missing
tokens or imputation.

These rows represent tumor samples collected at their harvesting time.
Identifiers retain the authors' L/R suffixes, and several share the same
numeric stem. Preparation preserves these identifiers and the experimental
conditions so downstream analyses can account for the study design.

## Preparation and relationship to Iowa's version

The source matrix contains 47,323 probes across 101 samples. GEO describes
the submitted processing as background correction, variance stabilization,
and robust spline normalization with Bioconductor's `lumi` package.
Preparation uses these processed values directly, without rerunning
normalization, filtering probes, standardizing columns, or applying another
logarithm to expression values.

Each probe is matched by its `ID_REF` to GPL10558's `ID` and assigned its
`ILMN_Gene` label. For each sample, probes sharing a label are averaged with
R's arithmetic `mean`. This yields 34,694 features. `ILMN_Gene` is the
platform's internal gene symbol, and these historical labels do not identify
34,694 distinct, current human genes. Labels such as `1-Mar` and `1-Dec`
are retained verbatim. Preparation does not infer repairs or update gene
annotations. Full probe sequences, descriptions, and other platform fields
are omitted from the portable table.

The original phenodata table is joined to the expression matrix using the
sample identifier in GEO's `!Sample_description`. All 101 identifiers match
uniquely. Treatment, day, and model are also checked against GEO's sample
source names. The response is computed with R's `log2` from the original
RTV measurements, and the six day-zero samples have response zero.

This follows the averaging and response definitions documented by Iowa.
Every expression predictor and response was compared with its pinned RDS
after matching feature names. Expression values match exactly; the largest
absolute response difference is `1.11e-16`, consistent with logarithm
implementations differing by about one binary64 rounding unit. Treatment
and day match exactly.
The portable table adds GEO sample accessions, the original sample identifier,
model, and untransformed RTV. Its predictor order is fixed independently of
locale, and it omits Iowa's nested `fData` annotation table.

## Included files and verification

- `data.csv.gz`: the portable dataset.
- `README.md`: this dataset documentation.
- `prepare.py`, `read_source.R`, `convert.R`, and `verify.R`: acquisition,
  preparation, and verification scripts.
- `provenance.json`: source and output hashes, environment, dimensions,
  preparation decisions, and canonical verification.
- `LICENSE`: the MIT license for the preparation code and documentation.

The scripts require the Datamonger repository and its devenv environment.
Run `prepare.py` from `curation/koussounadis2014/1/` in that repository,
passing a new output directory outside the working tree. It verifies the
size and SHA-256 of all three original sources before preparing the CSV.
Numeric serialization uses 17 significant digits for binary64 round trips.
R checks every restored value and metadata field against the prepared source,
and its canonical form 1 digest must equal Python's digest. Fixed gzip
metadata and pinned output hashes check repeatability. These checks validate
the conversion; independent registry release review remains separate.

## Citation and reuse terms

Koussounadis A, Langdon SP, Harrison DJ, and Smith VA (2014).
Chemotherapy-induced dynamic gene expression changes in vivo are prognostic
in ovarian cancer. *British Journal of Cancer* 110:2975–2984.
[doi:10.1038/bjc.2014.258](https://doi.org/10.1038/bjc.2014.258).
GEO accession: GSE49577. Illumina HumanHT-12 V4.0 platform: GPL10558.

Credit the study authors and GEO for the measurements, Illumina for the
platform identifiers, and Datamonger for the portable preparation. Iowa
Biostatistics provides the comparison reference.

The numeric extract and source identifiers are distributed on the basis of
[GEO's source terms](https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html).
GEO places no restrictions on use or distribution but warns that submitters
may retain intellectual property rights and that NCBI cannot grant
unrestricted permission on their behalf. No additional data-specific
restriction was found in the reviewed series, representative sample, or
platform records. No SPDX license or public-domain dedication is inferred.
The article's CC BY-NC-SA 3.0 license is not assumed to license the separate
GEO deposit. The accompanying MIT license covers the preparation code and
documentation.
