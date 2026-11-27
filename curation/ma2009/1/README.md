# Prepare URL Reputation

The registry identity is `datamonger:ma2009@1`. Use the
[UCI URL Reputation ZIP](https://archive.ics.uci.edu/static/public/187/url%2Breputation.zip).
UCI attributes the dataset to Justin Ma, Lawrence K. Saul, Stefan Savage,
and Geoffrey M. Voelker and publishes it under CC BY 4.0. The license
supports redistributing the dataset with attribution and a description
of the repackaging. [UCI license statement](https://archive.ics.uci.edu/dataset/187/url+reputation),
[CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/)

In the repository’s devenv shell, download the source outside the working
tree and stage the deposit files in a new directory.

```bash
stage=$(mktemp -d /dev/shm/datamonger-url-reputation.XXXXXXXX)
chmod 755 "$stage"
curl --fail --location \
  'https://archive.ics.uci.edu/static/public/187/url%2Breputation.zip' \
  --output "$stage/uci.zip"
uv run --project packages/python python curation/ma2009/1/prepare.py \
  "$stage/uci.zip" "$stage/deposit"
```

The recipe checks the source ZIP digest, extracts the 121 SVM-light day
files and `FeatureTypes`, and checks that each gzip file decompresses to
the original bytes. The staging directory’s `preparation.json` records the
source member hashes and the Python and zlib versions. Each part’s
`SHA256SUMS` covers its packaged files and public README.

The two Zenodo records cover [days 0–60](https://doi.org/10.5281/zenodo.24590923)
and [days 61–120](https://doi.org/10.5281/zenodo.24591026). The
[Zenodo file limit](https://help.zenodo.org/docs/deposit/manage-files/) is
100 per record, and each day requires a separate download. Both deposit
plans include the original `FeatureTypes` file for reference.

## Verify the published files

The [deposit receipt](zenodo-records.json) records the version-specific
DOIs, file-access review, and SHA-256 digests. Compare anonymous downloads
with the staged `SHA256SUMS` files. The
`named-splits` representation orders split names `Day0` through `Day120`
numerically and decodes each day with LIBSVM version 2. Its classification
task uses the day’s sparse matrix as features and the original integer
label as the target.

Re-fetch and decode all 121 registered day files with `dm-add`.

```bash
uv run --project packages/python python tools/dm_add.py \
  registry/datasets/datamonger/ma2009-1.yaml
```

The decoder should report 2,396,130 rows in total and 3,231,961 feature
positions per split. Follow the [registry review workflow](../../../CONTRIBUTING.md#adding-or-revising-a-dataset)
for independent release verification.
