# Datamonger

Retrieve public research datasets with a recorded registry, verified artifact
bytes, and consistent decoded values across languages.

Start with the [Python guide](python.md), [R guide](r.md), or
[Julia guide](julia.md). Use the [command-line client](cli.md) when you need
verified raw artifacts. This prototype brings the four client guides into one searchable site.

## Reproducible data access

A registry record fixes the source bytes, decoding recipe, expected shape, and
canonical digest of decoded values. Record the dataset version and the strong
registry selector with your analysis. A bare registry release name is a
lookup, not a cryptographic pin.

The language clients currently bundle `proof-0001`; the CLI bundles `2026.09`.
A bundled index works offline, but an uncached artifact requires access to its
upstream source. Dataset artifacts are not bundled.

## Understand the guarantees

Artifact hashes check bytes against the selected registry. Canonical digests
check decoded logical values. Neither authenticates a selector obtained from
an untrusted source nor grants permission to use a dataset.

Read the [trust model](https://github.com/jolars/datamonger/blob/main/TRUST.md)
and the [revision 1 specification](https://github.com/jolars/datamonger/tree/main/spec)
for the contracts and their limits. The
[contributor guide](https://github.com/jolars/datamonger/blob/main/CONTRIBUTING.md)
explains how to work on clients and registry records.
