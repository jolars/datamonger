# Datamonger operations runbook

This runbook covers registry construction and publication, scheduled upstream
verification, and response to published-data incidents. The normative release
and evolution rules remain in [`spec/`](spec/README.md); this document explains
how maintainers apply them.

## Operational invariants

- A published registry release is immutable. Never edit or replace its
  `index.json`, `selector.json`, Git tag, or GitHub Release asset.
- Generated indexes and selectors come only from `dm-index`; never edit them by
  hand.
- Upstream dataset artifacts are not stored in Git or attached to GitHub
  Releases. Small synthetic conformance fixtures stay in the test corpus; a
  registry release publishes only `index.json`.
- A registry digest establishes integrity relative to its selector, not the
  selector's authenticity.
- Canary failures are expected operational signals. Hermetic CI must not depend
  on live upstream availability.
- A verification record remains provisional until an independent
  implementation reproduces it.

## Prepare a registry release

Work from a clean branch based on the commit intended for publication.

1. Add or revise manifests under `registry/datasets` according to
   [CONTRIBUTING.md](CONTRIBUTING.md). Review identity, provenance, license,
   distribution, preservation, decoded shapes, representative values, and task
   roles.
2. Create a new directory under `registry/releases` with a `release.yaml` that
   conforms to
   [`spec/schema/release-source-v1.schema.json`](spec/schema/release-source-v1.schema.json).
   Use a new release identifier and a `sequence` greater than every historical
   baseline it follows. Set `tag` to the Git tag that will own the GitHub
   Release asset.
3. List every manifest included in the release, every default, and any approved
   errata. A later release may omit a dataset, but it may not mutate a repeated
   identity outside the evolution rules.
4. Generate the immutable index and selector from `packages/python`:

   ```console
   uv run python ../../tools/dm_index.py build \
     registry/releases/<release>/release.yaml
   ```

   For a production release, this also regenerates the mutable
   `registry/catalog.json`. The build refuses to replace an existing immutable
   generated file with different bytes.
5. Inspect the complete diff. Confirm that the selector's release and URL match
   `release.yaml`, and independently compute the index digest:

   ```console
   sha256sum ../../registry/releases/<release>/index.json
   uv run python ../../tools/dm_index.py check \
     registry/releases/<release>/release.yaml
   ```
6. Run the hermetic gate from the repository root:

   ```console
   devenv test
   ```
7. Re-run `dm-add` against each new or changed completed manifest. This
   re-fetches every declared location, requires identical bytes, and checks the
   recorded artifact and decoded expectations:

   ```console
   cd packages/python
   uv run python ../../tools/dm_add.py \
     ../../registry/datasets/<source>/<name>-<version>.yaml > /dev/null
   ```

   The full canary consumes the index from the selector's published URL, so it
   is the post-publication gate below rather than a pre-publication check.

Keep the human review record in the pull request. In particular, record who
reviewed licensing and preservation evidence and whether canonical verification
has been independently reproduced.

## Publish a prerelease

The repository currently publishes registry candidates as GitHub prereleases.
After the release commit is reviewed and present on the default branch:

1. Create and push the exact Git tag named by `release.yaml` at that commit.
2. Create a GitHub prerelease for that existing tag and upload the generated
   `index.json` as its sole asset, named `index.json`.
3. Confirm that the asset URL is byte-for-byte the `index_url` in
   `selector.json`. Download it, compute SHA-256, and compare the result with
   `index_sha256`.
4. Run `dm-canary` with the checked-in selector. This verifies the remote index,
   every declared location, decoded component expectations, and a supported
   canonical digest without consulting the artifact cache.
5. Confirm that the catalog on the default branch contains the exact selector.
   Resolve its bare release name with the Python client and compare the returned
   `Registry` with the checked-in selector.
6. Update `.github/workflows/upstream-verification.yml` when the newly published
   release becomes the active canary target. Add every released independent
   client to its implementation matrix.

Do not delete and recreate a release asset to fix a mistake. Follow the
correction procedure below.

## Cut a specification release candidate

A specification release candidate identifies one immutable Git commit. Before
tagging it:

1. Audit [`spec/revision-1.md`](spec/revision-1.md) against every normative
   Markdown contract, schema, and conformance descriptor named in its inventory.
2. Confirm that each wire and authoring document carries its own version and
   that clients reject unsupported versions rather than guessing semantics.
3. Run every revision 1 conformance case in the reference client and run the
   complete hermetic quality gate.
4. Verify that user, package, contributor, trust, and operations documentation
   agrees with the candidate behavior.
5. Record in the release notes the candidate identifier, commit, contract
   inventory, conformance schema version, paired registry selector, known
   limitations, and implementations that have passed conformance.
6. Create a new candidate tag and release. Never move or reuse a published
   candidate tag.

Every output-affecting correction after publication requires an updated
conformance corpus and a new candidate identifier and tag. Advance an affected
contract version when [`spec/revision-1.md`](spec/revision-1.md) requires it; an
implementation-only correction does not by itself redefine a contract. Never
rewrite the earlier candidate. Build and publish any paired registry candidate
through the registry procedure above.

## Tool behavior and exit status

`dm-add` writes a completed manifest to stdout unless `--output` is supplied and
writes its review report to stderr. It exits `0` on success and `2` when input,
retrieval, decoding, or output validation fails. `--force` is valid only with
`--output` and should be reserved for an intentional replacement of an
unpublished manifest.

`dm-index build` exits `0` after creating or confirming deterministic outputs
and `2` on invalid input or an attempted immutable replacement. `dm-index check`
never writes generated files; it exits `0` when all outputs are current, exits
`1` when an output is missing or stale, and exits `2` when validation cannot
complete.

`dm-canary` writes a complete Markdown report to stdout. It exits `0` when every
check passes, `1` when the report contains observed drift, and `2` when the
command or local selector is invalid. Registry-download and registry-integrity
failures are observed drift and therefore produce a report and exit `1`.

## Scheduled upstream verification

The upstream-verification workflow runs Mondays at 06:00 UTC and on manual
dispatch. For each implementation in its matrix, it:

- fetches the selected index from its published URL and verifies its digest;
- fetches every registered artifact location without using the cache;
- checks size, SHA-256, and declared file compression;
- decodes one verified artifact set per dataset;
- checks expected components and canonical SHA-256;
- publishes the Markdown report in the workflow summary;
- opens or updates one implementation-specific drift issue on failure; and
- closes the open drift issue after a successful recovery.

A failure in one location does not suppress later location or dataset checks.

Review every scheduled run. A green run is evidence of availability at that
time, not preservation. A red run should remain visible until either the
upstream recovers or a later registry release records an approved operational
change.

## Triage a canary failure

First preserve the complete report and classify the failing layer:

- **Registry index:** Check the published asset URL, digest, HTTP redirects, and
  embedded release. Do not replace the asset.
- **Location availability:** Check DNS, TLS, redirects, status, and transient
  upstream maintenance. Retry before changing metadata, but do not hide a
  persistent failure.
- **Artifact integrity:** Determine whether upstream bytes changed, HTTP
  `Content-Encoding` removed declared artifact compression, or a mirror serves
  different bytes. Never update a digest in place.
- **Dataset decoding:** Reproduce with the selector, saved bytes when lawful,
  the named decoder version, and the conformance suite. Separate malformed new
  upstream bytes from an implementation regression.
- **Implementation-only failure:** Compare the same strong selector and
  canonical record across all released clients. An implementation regression
  is fixed in that client; a contract ambiguity requires a corrected
  specification release candidate.

Record timestamps, affected selectors and dataset IDs, attempted locations,
expected and observed digests, client versions, and whether cached copies remain
usable. Do not attach data whose license or sensitivity forbids redistribution.

## Correct published information

Every correction is published in a new registry release. The required identity
and contract treatment depends on the change:

| Change | Required action |
| --- | --- |
| Add, remove, or reorder retrieval locations; clarify provenance, license, distribution, or preservation metadata | New registry release; retain the dataset version only if all release-evolution rules pass |
| Change artifact name, size, SHA-256, format, compression, or representation recipe | New dataset version and new registry release |
| Change task metadata or component expectations | Follow the append-only and erratum rules in `spec/identity.md`; publish a new registry release |
| Replace an incorrect verification record | Approved verification erratum that revokes the original and appends a replacement in a new registry release |
| Change decoded logical output | New decoder version, new dataset version, conformance updates, and a new specification release candidate |
| Change canonical bytes or error semantics | New affected contract version, conformance updates, and a new specification release candidate |
| Editorial clarification with no semantic effect | Review and publish with the existing contract version; document why it is non-semantic |

An erratum must conform to
[`spec/schema/erratum-v1.schema.json`](spec/schema/erratum-v1.schema.json), name
the affected release and exact original record, include its exact replacement
and reason, and record maintainer approval. Errata are append-only across later
releases.

If a dataset should no longer be offered by default, change the default or omit
the dataset in a later release. Existing selectors remain valid historical
records and are never redirected. If a legal or security concern requires an
advisory, publish it without redistributing restricted bytes and explain the
limits of any mitigation for already pinned releases.

## Recovery and housekeeping

There is no rollback that mutates an immutable release. Recovery means
publishing a later corrected release, updating the catalog, and moving the
scheduled canary target. Keep old selectors and release assets available so
published analyses remain auditable.

The Python cache evicts nothing automatically. Users can inspect and clean it
with `cache_info()` and `cache_clean()`; active objects are skipped. Operators
must not treat user caches as mirrors or backups. Durable preservation requires
an explicit reviewed deposit and corresponding registry metadata.

## Stable release gate

Do not promote revision 1 or its registry to stable until the R, Python, and
Julia clients pass the complete shared conformance corpus against the same
release candidate, independent implementations reproduce and review every
candidate verification record, and all corrections have been incorporated into
a new candidate. Coordinated client releases must bundle the same stable
registry selector.
