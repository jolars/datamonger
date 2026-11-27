# Preparing Yeoh2002

The dataset ID is `datamonger:yeoh2002@1`. It uses the `stjude`
object from Bioconductor's `stjudem` 1.16.0 source archive. The six-subtype
selection reproduces Iowa Biostatistics' measured cohort. `DATASET.md`
describes the data, and `RIGHTS.md` records the source license review.

## Reproduce and validate

Run from the repository root in its devenv shell.

```console
uv run --project packages/python python curation/yeoh2002/1/prepare.py /tmp/yeoh2002-reproduction
```

To reuse a local file, add `--source /path/to/stjudem_1.16.0.tar.gz`. The
recipe verifies the 28,928,034-byte archive and its SHA-256
`1b0a25f1ccf1f3d54f2430ed2a406d6afde25b32dddc0f64d525088fb07c0732`.
It decodes the generated CSV with Datamonger's delimited-text decoder and
compares every expression value to the binary64 bits from the R data object.
The compressed CSV is 27,814,418 bytes with SHA-256
`468b1df659efafcf6de42e1c3cadb51dfcabf3e3c187c6ada6eefffa16ef2758`.
Its canonical form 1 SHA-256 is
`968a0ab930759209d2487b0d99d7d7a04200c0407e8fa321a684957cdd387953`.

The output includes `provenance.json` and a metadata-only
`manifest.local.yaml` with the validated recipe, task roles, and component
expectations. Keep generated files outside the repository.

## Iowa comparison

The reference was downloaded from Iowa Biostatistics at commit
`f6b782b919a76898dbc1f0421e96274ef6987b6d`. Its SHA-256 is
`8cd8af74d71b99dddbfb0e784ed247542969c1c009392f0e5f774e864e45baca`.
In R, the transposed source subset is identical to Iowa's `X` matrix,
including its dimensions, names, order, and values. The source labels are
identical to the character values of Iowa's `y` factor.
[Iowa RDS](https://media.githubusercontent.com/media/IowaBiostat/data-sets/f6b782b919a76898dbc1f0421e96274ef6987b6d/Yeoh2002/Yeoh2002.rds),
[Iowa preparation script](https://github.com/IowaBiostat/data-sets/blob/f6b782b919a76898dbc1f0421e96274ef6987b6d/Yeoh2002/x.r).

## Deposit and registration

The version 1 Zenodo deposit contains the files listed in `DATASET.md`.
The public record and all seven files are accessible without credentials.
`zenodo-record.json` records the version DOI, the direct download URL for
registration, and the verified SHA-256 digests.
[Zenodo deposit](https://doi.org/10.5281/zenodo.24602156).

The production manifest is
`registry/datasets/datamonger/yeoh2002-1.yaml`. The collection selects this
dataset for the next registry release. Recheck the public download with
`dm-add` when auditing availability.
