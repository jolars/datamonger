# Rhee2006: Nelfinavir susceptibility and HIV protease mutations

This dataset contains HIV protease mutation indicators and Nelfinavir
susceptibility measurements from the Stanford HIV Drug Resistance Database.
Datamonger prepared this CSV from Stanford's original text data, following
Iowa Biostatistics' preparation for the Rhee2006 dataset.

Version: 1. DOI: [10.5281/zenodo.23398467](https://doi.org/10.5281/zenodo.23398467).

## Data

`data.csv` is a UTF-8 CSV with a header, 842 observations, and 362 columns.

- The first 361 columns are binary mutation indicators, stored as numeric
  values. A name such as `P13.V` denotes valine (`V`) at protease position 13.
  A value of 1 means that residue is present; 0 means it is absent from the
  source's residue notation. Mixed residues can activate multiple indicators
  at the same position.
- The final column, `y`, is the natural logarithm of Stanford's `NFV`
  susceptibility value. Larger values indicate greater drug resistance.

Rows preserve the order of the selected source observations. The CSV contains
no missing values. Isolate identifiers and susceptibility measurements for
other drugs are excluded. This representation supports regression with `y` as
the response and the mutation indicators as predictors.

For example, in Python:

```python
import pandas as pd

data = pd.read_csv("data.csv")
X = data.drop(columns="y")
y = data["y"]
```

In R:

```r
data <- read.csv("data.csv", check.names = FALSE)
X <- as.matrix(data[, names(data) != "y"])
y <- data$y
```

## Preparation and validation

The source is Stanford's [PI_DATA.txt](https://hivdb.stanford.edu/_wrapper/pages/published_analysis/genophenoPNAS2006/DATA/PI_DATA.txt).
Preparation follows [Iowa Biostatistics' script](https://github.com/IowaBiostat/data-sets/blob/f6b782b919a76898dbc1f0421e96274ef6987b6d/Rhee2006/data.R):
retain valid protease sequences, encode residue indicators, remove globally
absent indicators, compute `log(NFV)`, and exclude observations without an NFV
response. The indicator columns use mutation-major order, matching Iowa's
prepared data.

The CSV preserves every prepared binary64 value using 17 significant digits.
Its values, column names, and ordering match Iowa's RDS representation exactly.
The original prepared values and the R and Python CSV decoders produce the
same Datamonger canonical digest.

`data.csv` is 626,704 bytes, with SHA-256:

```text
893a104177f8d946fcd7ff429406757aa0d24be890982f0a7ee9cb9540ae00d3
```

The deposit also contains:

- `read_source.R` and `convert.R`: source preparation and CSV serialization.
- `verify.R`: comparison of the prepared values and decoded CSV using the R
  client and the expected canonical digest.
- `prepare.py`: orchestration within the Datamonger repository's development
  environment. It requires the repository and its R and Python packages.
- `provenance.json`: source and recipe hashes, R version, artifact details,
  canonical digest, and the reviewed redistribution basis.
- `RIGHTS.md`: the data rights statement and source terms.

To reproduce the data, use the [Datamonger repository](https://github.com/jolars/datamonger)
and its instructions in `curation/rhee2006/1/README.md`.
The original Stanford text file is retrieved during preparation and is not
included in this deposit.

## Citation and rights

Rhee S-Y, Taylor J, Wadhera G, Ben-Hur A, Brutlag DL, and Shafer RW (2006).
Genotypic predictors of human immunodeficiency virus type 1 drug resistance.
*Proceedings of the National Academy of Sciences*, 103:17355–17360.
[doi:10.1073/pnas.0607274103](https://doi.org/10.1073/pnas.0607274103).

Credit Stanford HIVDB for the source data, Iowa Biostatistics for the
preparation recipe, and Datamonger for this portable representation.

The data are redistributed on the basis of Stanford HIVDB's public-domain
statement for published data, as documented in `RIGHTS.md`. This does not assert
a CC0 dedication or apply the repository's MIT code license to the data.
