# Datamonger CLI

The standalone Rust CLI retrieves registered artifact bytes without requiring
Python. It verifies the selected registry index and each artifact's registered
size and SHA-256. It does not decode data or verify canonical logical values.

Build with `cargo build --release --locked` from this directory, then install
`target/release/datamonger` on your `PATH`. Tagged releases use `dist` to provide
archives and SHA-256 checksums for x64 Linux (static musl), x64 and ARM macOS,
and x64 Windows in [GitHub Releases](https://github.com/jolars/datamonger/releases).

The CLI bundles the stable `2026.09` registry index. Listing and inspecting
that registry work offline:

```console
datamonger list --source uci
datamonger info uci:iris
datamonger registry show
```

`fetch` retrieves every artifact in a dataset by default. Select one with
`--artifact`. Files go into a private content-addressed cache; `--output-dir`
also exports verified raw bytes under `SOURCE/NAME/VERSION/ARTIFACT.FORMAT`.
The CLI preserves an artifact's registered compression. It refuses to overwrite
an existing export.

```console
datamonger fetch libsvm:dna_scale --output-dir ./data
datamonger fetch libsvm:dna_scale --artifact train --json
datamonger --offline fetch uci:iris
datamonger cache list
datamonger cache clean --dataset uci:iris@1
```

Use `--json` for structured command results; errors are JSON on stderr. Use
`--cache-dir` to move the CLI cache. The CLI never reads another client's cache.

To pin a different registry, place a strong selector at
`.datamonger/selector.json` in a project directory or pass `--selector PATH`.
Project selectors are found from the current directory upward. Resolution
through the HTTPS catalog is explicit:

```console
datamonger registry resolve 2026.09 --output .datamonger/selector.json
datamonger --selector .datamonger/selector.json list
```

A selector fixes an index by SHA-256. Treat a selector obtained through an
untrusted channel as untrusted; the checksum alone does not authenticate its
publisher. See [TRUST.md](../../TRUST.md).
