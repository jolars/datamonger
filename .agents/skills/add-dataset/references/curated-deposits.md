# Curated representations and dataset deposits

Read this when an addition requires an authorized conversion or a
Datamonger-controlled deposit. These steps publish dataset artifacts, not a
registry release. Respect the stage the user requested: local preparation,
private draft, public publication, or correction of an existing deposit.
Continue within authorization already given; a token alone does not authorize
publication, and authorization to deposit data does not authorize a registry
release.

## Source, identity, and rights

- Prefer an original, documented source over a secondary binary export when
  it supplies the required data. Document preprocessing explicitly; different
  selections or transformations are different representations. Compare with
  the secondary export when equivalence matters.
- Pin source bytes by size and SHA-256. Use full Git commit URLs when relevant.
  Git LFS raw URLs can serve pointer files; retrieve actual content and verify
  its digest. Check responses even after HTTP 200, which can contain an HTML
  application instead of the requested data.
- Use `datamonger` as the source namespace for representations Datamonger
  curates and distributes. Preserve original authorship, sources, and prior
  preparation in provenance. Hosting alone does not change the namespace of an
  otherwise unchanged upstream entry.
- Review redistribution evidence for the source and derived representation.
  A provider's source terms or public-domain statement may supply the basis;
  a named license is not mandatory. Record the actual assessment and reviewer
  without inventing an attestation or assigning CC0, MIT, or another license
  unsupported by the evidence. If the basis remains unclear, finish local
  preparation and identify the specific unresolved issue before distribution.
  Follow [the trust model](../../../../TRUST.md#distribution-preservation-and-upstream-risk)
  for mirror and preservation claims.

## Prepare portable artifacts

Keep dataset-specific recipes, documentation, and deposit receipts under
`curation/<name>/<version>/`, with shared tooling in `tools/` and generated data
outside the working tree. Record the conversion environment. Convert once
during curation into a supported client representation; clients should not run
the conversion or require the
source language's runtime. An unsupported source format does not by itself
justify extending every client decoder.

Preserve values, names, ordering, missingness, labels, and documented splits.
Decide explicitly how IDs and sample or feature annotations are retained or
omitted. Record transformations and exclusions. Verify numeric precision and
repeatability, decode the result using the existing contract, and compare
canonical digests across implementations where available. Retain the normal
independent release-review requirement.

The [Rhee2006 workflow](../../../../curation/rhee2006/1/README.md) is an
example, not a universal format: it prepares a single numeric CSV from Stanford
text data and compares R and Python canonical values. Nested datasets may need
separate artifacts or a separately designed representation.

## Write documentation for dataset users

Prefer one self-contained README for dataset users in the deposit. Explain the
scientific data, dimensions, column meanings and units or transforms, missing
values, task roles, source, preparation, included files, verification, citation,
and applicable reuse terms. List only deposited files, and explain any repository
dependencies of attached reproduction scripts.

Keep the public documentation in Git alongside the preparation code. In this
repository, use `DATASET.md` for that document and upload it as `README.md`.
Keep the repository's `README.md` for maintainer instructions. These filenames
are a local convention, not Zenodo requirements.

Keep detailed rights evidence and review reasoning in Git, for example in
`RIGHTS.md`. Put the applicable terms and source links in the public README and
Zenodo's rights metadata. Deposit a separate license or rights file only when
the license requires it or substantial terms warrant it. When depositing
reproduction code, retain its license notices and distinguish its license from
the data terms.

Keep local manifests, sandbox setup, upload instructions, reviewer checklists,
and future registry steps in maintainer documentation. Avoid draft or private
status claims in permanent dataset documentation. Before publication, check the
record title, description, README, file inventory, provenance, and rights for
consistency; a verified CSV does not validate these documents.

## Deposit and verify

Zenodo is the design's preferred preservation host. Check current official
[API documentation](https://developers.zenodo.org/) and
[deposit guidance](https://help.zenodo.org/docs/deposit/) for the operations
needed; do not assume endpoints or policies are frozen.

- Use the configured token, such as `ZENODO_API_TOKEN`, through an authorization
  header without printing it. Personal tokens suffice for a maintainer's own
  deposits. Production and sandbox use separate accounts and tokens; a sandbox
  account is needed only for a sandbox trial.
- Reuse a recorded deposit ID when resuming. Record the ID and links promptly
  so an interrupted upload does not create duplicate deposits. Keep credentials
  out of receipts and repository files.
- Create the requested draft, upload a deliberate file set, and set attribution,
  source relationships, version, and reviewed rights. Zenodo supports custom
  rights statements when a standard license does not describe the evidence.
  Its legacy deposition API and modern record API use different schemas and
  media types; verify custom rights persisted in the record, not just the request.
- Before an authorized public publication, ensure file visibility permits
  anonymous downloads. A public record can still have restricted files. A
  private draft can be reviewed by its owner but is not a registry download
  location. Do not publish while rights or file validation remain unresolved.
- Download uploaded files and verify their hashes. After publication, confirm
  the final record status, version-specific DOI, rights, and intended access.
  For public retrieval, download the data without credentials and verify its
  SHA-256. Use direct version-specific HTTPS file URLs in manifests; the DOI is
  the citation, not an assumed download endpoint.
- Save a receipt with publication state, DOI, file-access state, and verified
  artifact hashes. Mark preservation `durable` only after the required review.
  Return to manifest authoring and collection validation when registration is
  in scope; dataset publication does not make it available through a registry.

For corrections, first read the published record and preserve edits made by the
user. Fix stale descriptions as well as attached documentation. Use Zenodo's
current minor-file correction procedure when eligible, retaining the DOI and
data hashes for a documentation correction. Changes to artifact identity or
the representation require a new dataset version under the identity contract.
Verify the published result and update the receipt; report any change that
could only be staged, rather than implying it is already public.
