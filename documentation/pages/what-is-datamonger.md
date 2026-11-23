# What is Datamonger?

Datamonger retrieves public research datasets in Python, R, and Julia. It
returns native data frames or sparse matrices and verifies that each client
decodes the same values. The standalone command-line tool retrieves verified
files in their registered format for use in scripts, pipelines, and other tools.

The [dataset catalog](../generated/datasets/index.md) lists available datasets
and their versions. Each dataset record describes its source, provenance,
license, and citations. You can inspect those details before downloading the
data.

Datamonger downloads files on first use, checks their size and SHA-256 digest,
and keeps them in a local cache. The clients bundle a registry snapshot, so
you can browse metadata and reuse cached files offline. Pin both the registry
and the dataset version to reproduce your data access across environments.

Follow [Getting started](getting-started.md) to install a client and retrieve
your first dataset.
