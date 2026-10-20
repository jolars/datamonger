# Preparing unscaled Gisette

The dataset identity is `datamonger:guyon2004-gisette@1`, following
the first author and year in the official NIPS 2004 proceedings. The suffix
distinguishes Gisette from the other datasets in that paper.

This preparation preserves the original UCI challenge feature values. It
does not use LIBSVM's scaled Gisette artifacts. `DATASET.md` contains the
dataset documentation, and `RIGHTS.md` records the source license evidence.
`preparation.json` records the reviewed local artifact hashes, split statistics,
environment, exact source comparisons, and successful repeatability check.

## Reproduce and verify

Run from the repository root in its devenv shell with new output directories
outside the working tree:

```console
uv run --project packages/python python curation/guyon2004-gisette/1/prepare.py /tmp/gisette-unscaled
uv run --project packages/python python curation/guyon2004-gisette/1/verify.py /tmp/gisette-unscaled
```

Pass `--source /path/to/gisette.zip` to reuse the pinned UCI archive. The
preparation verifies the archive's size and SHA-256, checks all split shapes
and the value sums supplied in `gisette.param`, and creates deterministic
gzip files. It then decodes them with the existing contracts. `verify.py`
independently reads the source with NumPy, compares all feature values and
available labels, and compares native Rust and independent Python canonical
encoders. The verifier uses `packages/python/tests/reference/_canonical.py`
from this repository; the scripts require the repository and its Python
development environment. These conversion checks are not an independent
registry-release attestation.

`provenance.json` records source member hashes, prepared artifact hashes,
split statistics, canonical digests, script hashes, and environment versions.
`verification.json` records the successful comparison. To check repeatability,
prepare a second bundle with the same source and compare all three data hashes.
The source ZIP remains in `sources/` for local provenance.

## Split encoding in the deposited preparation

`train.libsvm.gz` and `validation.libsvm.gz` preserve the 6,000 labeled training
rows and 1,000 labeled validation rows. No rows are concatenated or reassigned.
The `libsvm-split` decoder has fixed `train` and `test` input roles, so the local
manifest maps its `test` input to the validation artifact. Task metadata names
the semantic split `validation`; the public return field remains `data.test`.

`test-features.csv.gz` preserves the 6,500 original test rows without inventing
labels. `test-representation.local.yaml` describes its separately verified
CSV representation. The local manifest lists the artifact, but its labeled
representation does not consume or expose it.

The [named splits extension](../../../spec/decoders/named-splits-v1.md) now
supports a complete assembly: declare `train` and `validation` with their
LIBSVM recipes and `test` with its delimited feature-only recipe. The result
exposes all three provider names and retains the 6,500 test rows without labels.
This uses manifest schema 4. A future registered representation must use a new
dataset version because its recipe and logical output differ from version 1.

The local manifest uses `metadata-only` artifacts without download locations.
Do not select it in `registry/collection.yaml`. Production registration still
requires real version-specific artifact URLs, `dm-add`, collection validation,
and the normal release review.

## Published deposit

Version 1 was published on October 20, 2026, at
[doi:10.5281/zenodo.23508592](https://doi.org/10.5281/zenodo.23508592), following
the user's authorization. `zenodo-record.json` records publication, public
record and file visibility, scoped CC BY 4.0 data and MIT code/documentation
rights, and anonymous download verification of all nine files listed in
`DATASET.md`. Every file matched its prepared size and SHA-256, and the DOI
resolved anonymously to the published record.

The deposited scripts match the committed preparation recipes. The public
README adds the complete file inventory and reproduction instructions, and
the deposited provenance records its updated hash. `preparation.json` retains
the earlier local review receipt; `zenodo-record.json` records the final
published file hashes. The source ZIP, local decoding recipes, maintainer
README, source rights assessment, and repository receipts are not deposited.
The dataset has not been added to the production collection, and no registry
release was published.
