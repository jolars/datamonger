# Registry and Artifact Retrieval Version 1

This document is normative. Retrieval produces exact verified bytes; URLs are
locations and never identities.

## Registry selection and trust

A strong registry selector is `(release, index_sha256)`. Its versioned document
also carries `schema_version`; `index_url` is its retrieval location. Index and
artifact locations are absolute HTTP or HTTPS URLs with lower-case schemes. A
client must validate the release and lowercase SHA-256 grammars, hash the exact
retrieved index bytes before parsing them, parse the bytes as UTF-8 JSON, and
then require the embedded `release` and `schema_version` to match its supported
contract.

A bare release name resolved through an HTTPS catalog is a TLS-trusted
convenience lookup, not a cryptographic pin. Clients must expose the resulting
strong selector. A bundled selector inherits the trust of the package that
contains it. A digest proves integrity relative to that selector; it does not
authenticate the channel from which the selector came.

## Artifact byte boundary

An artifact is the response content after HTTP transfer framing and declared
HTTP content codings have been removed, but before manifest-declared artifact
compression is removed. Its `size` and `sha256` apply to those bytes.

For every HTTP request, a client must:

1. send `Accept-Encoding: identity`;
2. accept no content coding, `identity`, `gzip`, or the legacy alias `x-gzip`;
3. remove declared content codings in reverse application order;
4. reject malformed, truncated, concatenated, multiply declared, or unsupported
   coded streams; and
5. size-check and hash the decoded content incrementally.

Version 1 supports at most one non-identity content coding. Transfer coding and
`Content-Length` are transport metadata and are not included in artifact bytes.
Redirects may be followed under ordinary HTTP semantics; the final bytes must
still satisfy the registered size and digest.

Artifact compression is taken only from the manifest. It must not be inferred
from a URL, media type, or filename. Retrieval verifies and caches the
compressed artifact before a decoder removes `gzip` or `bzip2` compression.

## Location fallback

Locations are attempted in manifest order. A transport failure, unsupported or
malformed content coding, size mismatch, or digest mismatch discards the
temporary bytes and permits the next location to be tried. Invalid bytes must
never become a cache entry.

Location URLs must be unique within an artifact. A redirect target must also be
an absolute HTTP or HTTPS URL; redirects do not create or alter artifact
identity.

If all locations fail, diagnostics must retain each attempted location and
classify the result as an integrity failure when any location returned complete
but incorrectly sized or hashed bytes; otherwise it is an availability
failure. `metadata-only` artifacts fail before network access. Artifact
verification can never be disabled.

## Cache semantics

Registry indexes and artifacts are cached by SHA-256 in client-private cache
roots. A cache path is not proof of integrity: clients must recheck the complete
size and digest before use.

A download is written to a temporary file in the destination filesystem,
flushed, verified, and atomically published. Concurrent publishers may perform
duplicate work, but readers must observe either the previous complete object or
the new complete object—never a partial file. A corrupt existing object is
quarantined or removed before replacement.

Each client must implement per-object publisher, reader, and cleaner leases.
Publication excludes cleaners; an active reader excludes cleaners; cleaners
skip active objects. Lease recovery must distinguish a live owner from a stale
record after process or host failure. Client-specific paths and primitives may
differ, but these observable guarantees may not.

Offline retrieval uses verified cached indexes and artifacts only. It must not
silently select a different release or dataset version. Cache eviction is
manual, never automatic, and must report which objects were skipped because
they were active.

Decoded verification is enabled by default after retrieval and decoding. A
caller may explicitly disable only decoded verification; returned metadata
must then label the result as artifact-verified rather than decoded-verified.
