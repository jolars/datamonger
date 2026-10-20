# Gisette source rights review

The [UCI Gisette landing page](https://archive.ics.uci.edu/dataset/170/gisette)
explicitly licenses the dataset under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and attributes it to
Isabelle Guyon, Steve Gunn, Asa Ben-Hur, and Gideon Dror. The downloaded input
is the ZIP archive linked from that page. Its size, SHA-256, member inventory,
and member hashes are recorded by the preparation recipe and local receipt.

This review applies UCI's stated license to the source feature matrices and
available label files, and to their lossless LIBSVM and CSV representations.
Datamonger preserves the values, feature positions, example order, and source
splits. Removing explicit zeros from sparse storage, joining labels to their
corresponding rows, adding positional CSV headers, and compressing files do
not introduce a new scientific transformation.

Redistribution must retain author and source attribution, link CC BY 4.0,
and identify the format conversion. `DATASET.md` supplies that information.
The source archive, included PDF, and parameter file remain local provenance
and are not part of the proposed portable data file set. No LIBSVM-prepared
artifact or LIBSVM software license supplies the input values or rights basis.

Review performed by Codex (automated source review) on October 20, 2026.
This is a recorded source assessment, not an independent registry-release
attestation. The user authorized local preparation for review. No deposit,
publication, durable-preservation review, or download verification is claimed.
