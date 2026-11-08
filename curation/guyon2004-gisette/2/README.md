# Registering Gisette with named splits

The production identity is `datamonger:guyon2004-gisette@2`. Its manifest is
`registry/datasets/datamonger/guyon2004-gisette-2.yaml`, selected as the default
in `registry/collection.yaml` for the next registry release.

Version 2 uses the `named-splits` decoder to expose all three original splits:

- `train`: 6,000 rows and 5,000 sparse features, with original -1/+1 labels.
- `validation`: 1,000 rows and 5,000 sparse features, with original -1/+1 labels.
- `test`: 6,500 rows and 5,000 integer columns, without labels.

The classification task names features and targets within their corresponding
splits. The test split has feature roles only. Feature identities and the mapping
between label signs and digits remain unspecified by the source.

## Artifacts and version identity

The representation reuses the three unchanged artifacts deposited at
[doi:10.5281/zenodo.23508592](https://doi.org/10.5281/zenodo.23508592).
The deposit and its reproduction scripts remain version 1. No new deposit,
conversion, or scientific preprocessing is needed for this registry assembly.
The source license is CC BY 4.0; the [source review](../1/RIGHTS.md) and
[publication receipt](../1/zenodo-record.json) record the evidence.

The version 1 recipe maps validation to the decoder's fixed test field and
leaves the unlabeled test artifact outside its logical output. Version 2
preserves provider split names and exposes the test features. The changed
recipe and logical output require a new dataset version and canonical digest.

## Reproduce and validate

Follow the [version 1 preparation workflow](../1/README.md) to reproduce and
compare every feature value and available label with the pinned UCI source.
The reproduced data hashes must match the production manifest and published
receipt. The named-splits assembly changes component names and order, so its
canonical digest differs from the separate version 1 verification records.

Re-fetch and decode all production artifacts in the repository's devenv shell:

```console
uv run --project packages/python python tools/dm_add.py registry/datasets/datamonger/guyon2004-gisette-2.yaml --output /tmp/gisette-2-verified.yaml
```

Use a new output path. `dm-add` checks every pinned artifact and the complete
qualified component sequence and digest. Validate the selected collection
through the normal contribution workflow. These automated checks do not replace
the independent review required to publish a registry release.
