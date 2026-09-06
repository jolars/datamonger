# Datamonger trust model

Datamonger verifies that an analysis used the registry, artifact bytes, and
decoded logical values it names. Those checks are useful only when their trust
roots and limits remain explicit.

## Objects and trust roots

The verification chain has four distinct objects:

1. A registry selector names a release, the SHA-256 digest of its index, and a
   retrieval URL. The `(release, index_sha256)` pair is the strong selector.
2. The immutable registry index contains dataset identities, artifact sizes and
   SHA-256 digests, decoder recipes, expected structures, and decoded
   verification records.
3. An artifact is the exact content after HTTP transfer framing and content
   coding have been removed, but before manifest-declared file compression is
   removed.
4. The canonical logical form is a versioned byte stream derived from decoded
   components. Its SHA-256 digest detects logical-value or structural
   disagreement across implementations after artifact verification succeeds.

The initial trust root is the channel that supplies the strong selector:

- A selector bundled in a client package inherits the trust placed in that
  package and its distribution channel.
- A selector checked into a project inherits the trust placed in that project
  revision.
- A selector copied from a paper or another record inherits the trust placed in
  that record.
- A selector discovered by bare release name in the HTTPS catalog is
  authenticated only by that TLS exchange. Record and reuse the resolved
  selector when reproducibility matters.

A digest received alongside malicious replacement content does not authenticate
that content. The bundled snapshot also does not authenticate later snapshots,
because revision 1 has no signed or authenticated forward link between them.

## Guarantees and non-guarantees

| Mechanism | What it establishes | What it does not establish |
| --- | --- | --- |
| Strong registry selector | Exact index bytes and embedded release, relative to a trusted selector | Who authored the selector, or whether its metadata is true |
| Artifact size and SHA-256 | Exact retrieved or cached artifact bytes relative to the index | License, safety, availability, or preservation |
| Decoder recipe and component expectations | The intended versioned interpretation and shape | Scientific suitability or freedom from upstream errors |
| Canonical SHA-256 | Exact decoded logical values under a named canonical-form version | Independent attestation when computed only by the authoring implementation |
| HTTPS catalog lookup | Authentication and confidentiality of that lookup under the Web PKI | A permanent pin or protection after the catalog later changes |
| Scheduled canary | Recent upstream availability and agreement with registered bytes | Future availability or preservation |

Cryptographic hashes are integrity mechanisms, not signatures. Registry
signing is outside revision 1.

## Retrieval and cache boundary

Clients verify a registry index before parsing it and verify every artifact
before decoding it. Invalid downloads are discarded rather than published to
the cache. Cache paths are content-addressed, but path names are not trusted;
clients rehash cached content before use.

Publication uses temporary files, validation, and atomic replacement. Per-object
leases keep cleaners from removing an object while it is being published or
read. These guarantees assume that the private cache root is on a filesystem
with working local advisory locks and atomic replacement. They do not make a
shared or hostile cache directory safe.

Use `offline=True` when an operation must not access the network. Offline mode
does not select a fallback registry or dataset; it succeeds only with the
selected bundled or previously cached, verified content.

## Distribution, preservation, and upstream risk

Distribution policy and preservation status are independent of integrity:

- `metadata-only` means the client must not retrieve the artifact.
- `upstream-only` means the registry records an upstream location but does not
  provide a Datamonger-controlled copy.
- `mirror` means a reviewed mirror location may distribute the artifact under
  the recorded policy.
- Preservation status `durable` requires a reviewed durable deposit. A mirror
  without that record is not a preservation guarantee.

The current proof and candidate registry artifacts are upstream-only. Their
digests can detect upstream drift, but they cannot recover bytes that disappear.
A user's verified local cache may permit offline reuse, but it is not a project
preservation service.

The canary checks each registered location without using the artifact cache and
then decodes one verified copy. A failure may reveal downtime, changed bytes,
changed HTTP coding, or decoder disagreement. It is an operational signal; it
does not retroactively invalidate immutable earlier release bytes.

## Provenance, licensing, and scientific use

Registry records report evidence; they do not transfer ownership or grant
rights. A `known` license record identifies the reviewed license evidence. An
`unknown` status means that a user must establish permission independently
before downloading or using the data. Artifact-level terms may be narrower than
dataset-level metadata and take precedence for that artifact.

Artifact and canonical verification do not show that upstream measurements are
correct, representative, unbiased, safe, or fit for a particular scientific
purpose. Review provenance, collection methods, task definitions, and
limitations before analysis.

## Reproducibility record

For a reproducible result, retain at least:

- the canonical dataset identifier, including its explicit version;
- the registry release and index SHA-256;
- the complete selector, including its URL, in project configuration;
- every artifact digest used;
- whether decoded verification was performed; and
- the canonical-form version and digest reported by the client.

`fetch_data(..., return_info=True)` reports these values in the Python client.
If long-term availability matters, arrange lawful preservation separately; a
selector and hashes alone cannot reconstruct missing data.

## Reporting a trust problem

Report incorrect metadata, unexpected drift, or unavailable upstream content in
the repository's [GitHub issue tracker](https://github.com/jolars/datamonger/issues).
Avoid publicly attaching restricted dataset bytes. If a report contains an
exploitable client vulnerability or sensitive information, submit a
[private vulnerability report](https://github.com/jolars/datamonger/security/advisories/new)
instead of a public issue.

Published indexes, selectors, tags, and release assets are immutable. A
confirmed problem is documented and corrected in a later release under the
procedures in [OPERATIONS.md](OPERATIONS.md); the affected bytes are never
silently replaced.
