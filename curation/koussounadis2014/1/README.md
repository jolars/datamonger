# Preparing Koussounadis2014 from the original sources

The dataset is `datamonger:koussounadis2014@1`, published on
[Zenodo](https://doi.org/10.5281/zenodo.23468640) with public record and file
access. All preparation inputs come from NCBI GEO: the authors' GSE49577
expression matrix, its phenodata table, and the GPL10558 platform.
`DATASET.md` documents the measurements, averaging, metadata, task, and reuse
terms. `RIGHTS.md` records the automated source-policy review, and
`zenodo-record.json` records publication and anonymous download verification.

## Reproduce and validate

Run from the repository root in its devenv shell:

```console
uv run --project packages/python python curation/koussounadis2014/1/prepare.py /tmp/koussounadis2014-reproduction
```

To reuse downloaded sources, pass `--sources /path/to/source-directory`.
`prepare.py` records all three source URLs, sizes, and SHA-256 pins. Both
acquisition paths require the reviewed bytes. GEO may regenerate exports or
update associated metadata; a source mismatch requires review rather than
bypassing the pins.

The output contains a CSV with 101 rows, 34,694 expression predictors,
regression response `y = log2(RTV)`, and six metadata columns. Metadata stays
outside the default model features. Predictor labels follow ASCII byte order,
and samples retain GEO's source order. R verifies every value against the
prepared sources, and R and Python canonical digests must agree. Run twice
and compare the `data.csv.gz` hashes to verify repeatability.

The CSV is 64,071,973 bytes with SHA-256
`4eea58215f27cfa4085a1b90ebb57ab71866a0b16fbc9e39d6f211e66b6f20e0`.
The compressed artifact is 22,869,710 bytes with SHA-256
`d532f3aeb8159a7c44ab8e2fc4e4104f923c436a1001eb0c7c2e8abaa02f9c56`.
Canonical form 1 SHA-256 is
`59f7c34a97f9368c1947cc8e5339a01e31452f4493911ed1d714aada5fe11e59`.

The preparation creates the deposit's eight files, plus a
`sources/` directory and `manifest.local.yaml`. Generated files and source
downloads remain outside the repository. The local manifest uses
`metadata-only` with no download locations.

## Optional comparison with Iowa

Iowa's reference is pinned to commit
`f6b782b919a76898dbc1f0421e96274ef6987b6d`. Download its actual LFS content
from:

```text
https://media.githubusercontent.com/media/IowaBiostat/data-sets/f6b782b919a76898dbc1f0421e96274ef6987b6d/Koussounadis2014/Koussounadis2014.rds
```

Verify its 32,703,522-byte size and SHA-256
`d618fbb3b66096523df3029aab0d1e948f68eed2fa8392e50b1380ce46f77722`.
Then run:

```console
Rscript curation/koussounadis2014/1/compare_reference.R /path/to/GSE49577_series_matrix.txt.gz /path/to/GPL10558.txt /path/to/GSE49577_phenodata_matrix.txt.gz /path/to/Koussounadis2014.rds curation/koussounadis2014/1/read_source.R
```

The comparison matches all 101 samples and 34,694 predictor names, checks
every expression value within `1e-12`, and checks `y` within `1e-14` to
allow arithmetic differences across runtime versions. Treatment and day
must match exactly. The original and Iowa phenodata tables also match byte
for byte after decompressing GEO's file. Iowa is not required to reproduce
the portable artifact.

## Deposit and registration

The deposit contains the eight files listed in `DATASET.md`, with that
document uploaded as `README.md`. All eight were downloaded anonymously and
verified after publication. This maintainer README, rights review, comparison
script, source downloads, and local manifest stay outside the deposit. Custom
data rights record the qualified GEO source terms described in `RIGHTS.md`;
the separate MIT license covers the code and documentation.

The production manifest is
`registry/datasets/datamonger/koussounadis2014-1.yaml`. It uses the verified
public, version-specific Zenodo URL and records the deposit review. Recheck it
with `dm-add` when auditing availability. `registry/collection.yaml` selects
the dataset for the next registry release. Dataset publication does not
publish a registry release; the independent release review remains required.
