# Preparing unscaled Gisette

The proposed dataset identity is `datamonger:guyon2004-gisette@1`, following
the first author and year in the official NIPS 2004 proceedings. The suffix
distinguishes Gisette from the other datasets in that paper. No matching
identity exists in the registry or curation directories.

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

## Splits and the current decoder limit

`train.libsvm.gz` and `validation.libsvm.gz` preserve the 6,000 labeled training
rows and 1,000 labeled validation rows. No rows are concatenated or reassigned.
The `libsvm-split` decoder has fixed `train` and `test` input roles, so the local
manifest maps its `test` input to the validation artifact. Task metadata names
the semantic split `validation`; the public return field remains `data.test`.

`test-features.csv.gz` preserves the 6,500 original test rows without inventing
labels. `test-representation.local.yaml` describes its separately verified
CSV representation. The local manifest lists the artifact, but its labeled
representation does not consume or expose it. There is no general three-split
assembly or unlabeled LIBSVM input in the existing decoder contracts. Review
how to expose this artifact before registering the full dataset.

The local manifest uses `metadata-only` artifacts without download locations.
Do not select it in `registry/collection.yaml`. No files have been deposited
or published. A later authorized deposit needs a deliberate public file set,
consistent metadata and attribution, and anonymous download verification.
Production registration still requires real version-specific artifact URLs,
`dm-add`, collection validation, and the normal release review.
