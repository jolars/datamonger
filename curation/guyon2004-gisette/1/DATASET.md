# Gisette: original challenge feature values

Gisette is a binary classification benchmark for distinguishing handwritten
digits 4 and 9. Isabelle Guyon, Steve Gunn, Asa Ben-Hur, and Gideon Dror
distributed it for the NIPS 2003 feature selection challenge. This
representation preserves the integer features supplied by the
[UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/170/gisette),
before LIBSVM's additional feature scaling.

## Data and splits

| File | Rows | Features | Labels |
| --- | ---: | ---: | --- |
| `train.libsvm.gz` | 6,000 | 5,000 | 3,000 each of `-1` and `+1` |
| `validation.libsvm.gz` | 1,000 | 5,000 | 500 each of `-1` and `+1` |
| `test-features.csv.gz` | 6,500 | 5,000 | Unavailable |

The other six files are `README.md` (this document), `prepare.py` and
`verify.py` (reproduction and verification scripts), `provenance.json`
(source, artifact, and environment records), `verification.json` (conversion
check results), and `LICENSE` (the MIT license for code and documentation).

Every feature value is an integer from 0 through 999. There are no missing
feature values. Feature positions, example order, original split membership,
and available labels are preserved. The digit associated with each label
sign has not been established; retain the original signs when modeling.

The challenge producers had already normalized and centered the digit images,
sampled pixels, created higher-order pixel products, added distractor probes,
and randomized feature and example order. These are prepared challenge
features, not raw image pixels. Feature identities, units, and a feature-by-feature
mapping to signal or distractor roles are unavailable. Datamonger adds no
scaling, centering, imputation, feature selection, or label remapping.

In the LIBSVM files, each row begins with the original class label. Nonzero
features follow as increasing, one-based `index:value` pairs. Unstored features
are exactly zero. The declared feature dimension is always 5,000, including
any feature position absent from a split. Existing Datamonger LIBSVM decoders
return float64 features; these small integer values are represented exactly.
Labels decode as int64.

The test CSV has the header `x1,x2,...,x5000`, where each name identifies the
corresponding one-based source feature position. All fields decode as int64.
It has no target column, synthetic label, sample identifier, or split column.
The original test labels remain withheld by the source.

The task uses all 5,000 features to predict the original binary label. Training
and validation remain separate. The current Datamonger split decoder exposes
the validation artifact through its fixed `test` field; semantic task metadata
calls this split `validation`. The original unlabeled test CSV is a separate
file and is not included in that decoder's returned object.

## Preparation and verification

The input is UCI's
[`gisette.zip`](https://archive.ics.uci.edu/static/public/170/gisette.zip),
21,298,687 bytes, with SHA-256
`430bb631b3e494659f13763c117f06f5aa8a269b0d8e13ccf5b71d95303f3808`.
The recipe joins each labeled matrix with its matching label file, omits
structural zeros from LIBSVM storage, gives test features positional CSV
names, and compresses the three files with fixed gzip metadata. No numeric
precision is lost. No samples or features are excluded.

`prepare.py` checks source hashes, dimensions, label counts, and the source's
integer checksums. `verify.py` compares every feature value and available
label with an independent NumPy read of the source, checks decoded canonical
digests, and compares Rust and Python canonical encoders. Reproduction requires
the [Datamonger repository](https://github.com/jolars/datamonger), including
its `tools/` and `packages/python/tests/reference/` modules, and its Python
development environment. The deposited scripts match the
[committed preparation recipes](https://github.com/jolars/datamonger/tree/377466862d1fdc3d7f36a4cb514898196487055c/curation/guyon2004-gisette/1).
Run the recipes from their location in that checkout, using a new output
directory outside the repository:

```console
uv run --project packages/python python curation/guyon2004-gisette/1/prepare.py /tmp/gisette-reproduction
uv run --project packages/python python curation/guyon2004-gisette/1/verify.py /tmp/gisette-reproduction
```

The preparation downloads the pinned source and creates the local decoding
recipes needed by the verifier. `provenance.json` records hashes and environment
versions, and `verification.json` records successful conversion verification.

## Citation and reuse

Guyon, I., Gunn, S., Ben-Hur, A., and Dror, G. (2004). *Gisette* [Dataset].
UCI Machine Learning Repository. [doi:10.24432/C5HP5B](https://doi.org/10.24432/C5HP5B).

Guyon, I., Gunn, S., Ben-Hur, A., and Dror, G. (2004).
[*Result Analysis of the NIPS 2003 Feature Selection Challenge*](https://proceedings.neurips.cc/paper_files/paper/2004/hash/5e751896e527c862bf67251a474b3819-Abstract.html).
Advances in Neural Information Processing Systems 17, 545–552.

UCI licenses Gisette under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
Credit the original authors and UCI, link the license, and identify this
lossless conversion and compression when redistributing it. Datamonger is
the curator of this representation. The preparation scripts and accompanying
documentation use the MIT license in `LICENSE`; that license does not replace
the dataset's CC BY 4.0 terms.
