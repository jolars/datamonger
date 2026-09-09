# Registry releases

Versionary owns registry release PRs, changelogs, tags, and draft GitHub Releases.
The publisher validates the tagged snapshot, attaches `index.json`, verifies
the uploaded digest, and publishes the draft. See the
[operations runbook](../OPERATIONS.md#prepare-a-registry-release) for the process
and required independent review.

- `datasets/` contains dataset manifests.
- `collection.yaml` selects the manifests, defaults, and errata for the next
  release. It uses the release-source fields other than `release`, `sequence`,
  and `tag`, which the release generator supplies.
- `version.txt` is the registry version maintained by Versionary's `simple`
  strategy. Registry versions do not determine dataset or specification versions.
- `releases/<version>/` contains immutable generated release sources, indexes,
  and selectors. These are generated and reviewed in the registry release PR.
- `catalog.json` lists the strong selectors for checked-in releases.
- `latest.json` is the selector chosen for scheduled verification. Release
  preparation updates it alongside the catalog; it is not a permanent project pin.

Use `feat(registry): ...` for added datasets or capabilities and
`fix(registry): ...` for compatible corrections. Versionary scopes commits by
paths, so those changes must touch the registry's authoring files. Published
identities and indexes remain immutable regardless of the version bump. An
incompatible registry change requires the appropriate major bump and any
separately required dataset or contract versions.

The historical stable release `2026.09` is the Versionary `1.0.0` baseline.
Its existing tag, selector, and index are unchanged. This bookkeeping does not
publish a second registry or create a `1.0.0` selector. Future releases use
semantic identifiers such as `1.1.0` and tags such as `registry-v1.1.0`.

Clients continue to select a registry by its release identifier and index
SHA-256. A new registry release does not automatically release client packages.
