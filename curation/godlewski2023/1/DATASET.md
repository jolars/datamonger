# Brain tumor plasma metabolomics (Godlewski et al., 2023)

This is a lossless CSV representation of Supplementary Table S2 from
[Godlewski et al. (2023)](https://doi.org/10.1038/s41598-023-38243-1).
It contains measurements of 138 plasma metabolites in 235 samples from
patients with gliomas, patients with meningioma, and healthy controls.
Datamonger representation version: 1. Dataset ID: `datamonger:godlewski2023@1`.

## Data and task

`data.csv.gz` decompresses to a UTF-8 CSV with one header row, 235 observations,
and 140 columns in the original workbook order:

- `Sample Name`: the source's integer sample identifier, from 1 through 235.
  Retain it as metadata and exclude it from model features.
- `Sample type`: the original classification label, stored as text.
- The remaining 138 columns: numeric metabolite measurements. Column names
  identify the metabolites exactly as in the workbook, from `Carnitine` to
  `Hexoses`. Values retain the source's scale and precision. The workbook does
  not specify a unit in its headers; this conversion does not assign or change
  measurement units.

| Original label | Samples |
| --- | ---: |
| Glioma grade 1 | 3 |
| Glioma grade 2 | 15 |
| Glioma grade 3 | 10 |
| Glioma grade 4 | 66 |
| Meningioma | 70 |
| Healthy control | 71 |

The default classification task predicts `Sample type` from the 138 metabolite
columns. There are no missing values or predefined training and test splits.
The table preserves the six source labels rather than collapsing grades or
creating a binary diagnosis. It also retains the meningioma samples omitted
from the SLOPE package's binary example.

The paper reports 95 glioma patients, whereas Table S2 supplies 94 glioma
rows and 235 rows overall. The reason for this discrepancy is not established.
The CSV preserves the supplied table without adding or removing observations.

For example, in Python:

```python
import pandas as pd

data = pd.read_csv("data.csv.gz")
X = data.drop(columns=["Sample Name", "Sample type"])
y = data["Sample type"]
```

## Source and preparation

The original source is the publisher's
[Supplementary Table S2 workbook](https://static-content.springer.com/esm/art%3A10.1038%2Fs41598-023-38243-1/MediaObjects/41598_2023_38243_MOESM2_ESM.xlsx),
which contains one sheet, `Sheet1`. Its size is 226,198 bytes, and its SHA-256 is
`8b532fe953400725c5e5e13541adf984652954ff7ee8c71618381eddd9ada717`.

These are processed measurements rather than raw mass spectra. The authors
used the Biocrates AbsoluteIDQ p180 kit and MetIDQ software, normalized the
measurements according to the kit manual, retained metabolites detected in at
least 80% of samples, and filled missing measurements with half the applicable
metabolite and batch limit of detection. These upstream operations yielded
the published 138-metabolite table.

Datamonger changes only the file format and compression. It copies the
workbook's stored numeric text into CSV fields without rounding and retains
every header, label, sample ID, measurement, and row and column position.
It does not filter, normalize, scale, center, impute, select metabolites,
or map labels. Workbook formatting is not part of the CSV representation.

The paper has one sample-level metabolomics table. Supplementary Table S1
contains pathway-analysis results, which are not included in this dataset.
The paper's multiple classification experiments are derived comparisons
within the cohort, not separate source datasets deposited here.

## Files and verification

The deposit includes:

- `data.csv.gz`: the complete converted table.
- `README.md`: this document.
- `prepare.py`: source retrieval, pin verification, exact conversion, and
  generation of local manifest and provenance records.
- `verify.py`: an independent comparison of every CSV cell with an openpyxl
  reading of the original workbook, including binary64 equality for numbers.
- `verify.R`: agreement of the R and Python Datamonger decoder digests.
- `provenance.json`: source and artifact sizes and hashes, conversion
  environment, label counts, and canonical verification digest.
- `LICENSE`: the MIT license for the preparation code and documentation.

The original workbook is retrieved during preparation and is not included in
this deposit. Source bytes and generated artifacts stay outside the Git
working tree. Reproduction requires the
[Datamonger repository](https://github.com/jolars/datamonger) and its development
environment; follow `curation/godlewski2023/1/README.md` there. `verify.py` additionally
uses openpyxl 3.1.5, declared in its inline script metadata. Client retrieval
does not require Excel software, openpyxl, or running a conversion.

Preparation validates the CSV through the existing delimited-text decoder.
Repeated conversion must produce identical artifact hashes. These checks
establish representation integrity, not independent scientific validation
or an independent registry-release attestation.

The compressed artifact is 78,841 bytes with SHA-256
`1e65240b2b258bf32f85eac48518bea57e6579ebce3911daec783e07c38ecfcb`.
Its canonical form 1 SHA-256 is
`f487f2465c157a250795bdcea53ac3bb935e4b8a41d93a8f3fd7d5286294f287`.

## Citation and reuse terms

Godlewski A, Czajkowski M, Mojsak P, Pienkowski T, Gosk W, Lyson T,
Mariak Z, Reszec J, Kondraciuk M, Kaminski K, Kretowski M, Moniuszko M,
Kretowski A, and Ciborowski M (2023). A comparison of different
machine-learning techniques for the selection of a panel of metabolites
allowing early detection of brain tumors. *Scientific Reports* 13:11044.
[doi:10.1038/s41598-023-38243-1](https://doi.org/10.1038/s41598-023-38243-1).
Source: Supplementary Table S2.

The source article and its supplementary table are available under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Credit the original authors and source, link the license, and identify the
change from XLSX to CSV with gzip compression. Credit Datamonger for the
portable representation. The repository's MIT license applies to the new
preparation code and documentation, not to the source data.
