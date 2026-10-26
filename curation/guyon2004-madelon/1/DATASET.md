# Madelon: original UCI challenge splits

Madelon is an artificial binary classification benchmark from the NIPS 2003
feature selection challenge. This conversion preserves the original values
and splits distributed by the [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/171/madelon).

| File | Rows | Features | Labels |
| --- | ---: | ---: | --- |
| `train.csv.gz` | 2,000 | 500 | 1,000 each of -1 and +1 |
| `validation.csv.gz` | 600 | 500 | 300 each of -1 and +1 |
| `test.csv.gz` | 1,800 | 500 | Unavailable |

The source generates clusters on a five-dimensional hypercube, adds 15 linear
combinations of the five informative features and 480 distractors, and
randomizes feature and example order. The 500 supplied feature values are
integers from 0 through 999, with no missing values. Physical units and the
mapping of feature positions to informative or distractor roles are unavailable.
The target identifies the original two synthetic classes.

Each gzip-compressed CSV has a UTF-8 header and LF line endings. Columns `x1`
through `x500` identify the corresponding one-based source feature positions.
Training and validation append `response`, preserving the original -1/+1
labels. The test file contains only features; no labels are fabricated.
All columns decode as int64. All feature columns participate in the
classification task. Row order, feature order, and split membership are
unchanged. Datamonger applies no scaling, filtering, imputation, feature
selection, or label remapping. In particular, this conversion does not use
LIBSVM's prepared feature values.

The input is UCI's [`madelon.zip`](https://archive.ics.uci.edu/static/public/171/madelon.zip),
3,040,503 bytes, with SHA-256
`eb99a0153ebe7d9f4e74551b4b10c54a958b2990b156ce7d76b4e8d71a6f6e82`.
The recipe joins each labeled matrix with its matching labels, adds positional
headers, and compresses with fixed gzip metadata. It excludes no rows or
features. The source's PDF and parameter file are retained inside the local
source ZIP rather than converted into data columns.

Reproduction instructions and the preparation script are in
`curation/guyon2004-madelon/1/` of the Datamonger repository. Preparation checks
every value against an independent source read, verifies source checksums,
and compares the native and reference canonical encoders. The local provenance
record captures the exact source, outputs, and environment.

The bundle also contains `README.md` (this document), `prepare.py` (the
conversion and verification recipe), `provenance.json` (source, environment,
artifact hashes, and verification results), and `LICENSE` (MIT terms for code
and documentation). These accompany the three CSV files listed above.

Reproduction requires the [Datamonger repository](https://github.com/jolars/datamonger),
including `tools/`, `packages/python/tests/reference/`, and the Python client
in its devenv development environment. Run the script from its repository
location, with a new output directory outside the checkout:

```console
uv run --project packages/python python curation/guyon2004-madelon/1/prepare.py /tmp/madelon-reproduction
```

The recipe downloads and checks the pinned archive. Add
`--source /path/to/madelon.zip` to reuse it offline. The output also includes
the retained source ZIP and a local manifest for decoding; these local
authoring files are not included in this bundle. The named-splits assembly
exposes `train`, `validation`, and the feature-only `test` under their original
semantic names.

## Citation and reuse

Guyon, I. (2004). *Madelon* [Dataset]. UCI Machine Learning Repository.
[doi:10.24432/C5602H](https://doi.org/10.24432/C5602H).

UCI explicitly licenses this dataset under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Credit Isabelle Guyon and UCI, link the license, and identify the lossless file
conversion and compression when redistributing this representation.

The preparation code and accompanying documentation use the MIT license
in `LICENSE`. Those terms do not replace the data's CC BY 4.0 license.
