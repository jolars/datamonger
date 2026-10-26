# Maintaining the Madelon conversion

The curated identity is `datamonger:guyon2004-madelon@1`. The descriptive
suffix distinguishes this dataset from Gisette, another dataset from the same
2004 challenge paper. The dataset is published at
[doi:10.5281/zenodo.23665387](https://doi.org/10.5281/zenodo.23665387).
`zenodo-record.json` records public access and anonymous download verification
for all seven deposited files. The registry manifest selects the published
artifacts for the next registry release. `DATASET.md` documents the data for
users; `preparation.json` records the earlier local preparation results.

Run from the repository root in its devenv shell, using a new output directory
outside the working tree:

```console
uv run --project packages/python python curation/guyon2004-madelon/1/prepare.py /tmp/madelon-reproduction
```

For offline reproduction, append `--source /path/to/madelon.zip`. The script
checks the source ZIP's pinned size and SHA-256 before converting anything.
It writes `train.csv.gz`, `validation.csv.gz`, and `test.csv.gz`, retaining the
ZIP for local provenance. Each run compares all 2,200,000 feature values and
2,600 labels with an independent NumPy read of the source, checks the published
integer checksums, and compares Rust and reference Python canonical encoders.
Run twice and compare the data hashes to check byte repeatability in the
recorded Python and zlib environment.

`manifest.local.yaml` describes the complete assembly using `named-splits`
version 1 and `delimited-text` version 1 children. Features are int64 columns
`x1` through `x500`. Training and validation also have an int64 `response`.
The classification task retains the feature-only test split without a target.
The local manifest uses metadata-only artifacts and no download locations.
The production manifest uses the verified version-specific Zenodo URLs.
`provenance.json` records source member hashes, artifact hashes, split
statistics, environment versions, and
verification results. These checks are conversion validation, not an independent
registry-release attestation.

The script requires this checkout's `tools/`, Python client and reference test
modules, and Python development dependencies. Generated data stay outside Git.
The preparation command performs no upload. The deposit contains the three
CSV files, `DATASET.md` as `README.md`, `prepare.py`, `provenance.json`, and
the MIT `LICENSE` for code and documentation. Source data remain CC BY 4.0.
Publication does not publish a registry release; that still requires the
normal independent release review.
