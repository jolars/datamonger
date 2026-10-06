# Command-line guide

The standalone Rust CLI downloads verified raw artifacts. It checks artifact
size and SHA-256 but does not decode datasets or check canonical logical values.

Build from the Datamonger repository root:

```console
cargo build --release --locked --manifest-path packages/cli/Cargo.toml
```

Use the binary at `packages/cli/target/release/datamonger`, or install it on your
`PATH`. The bundled `2026.09` registry supports offline listing and inspection:

```console
datamonger list --source uci
datamonger info uci:iris
datamonger registry show
```

Download and export verified artifact bytes:

```console
datamonger fetch uci:iris --output-dir ./data
```

The CLI preserves registered compression and refuses to overwrite an existing
export. Uncached artifacts require network access.

See the [complete CLI guide](https://github.com/jolars/datamonger/blob/main/packages/cli/README.md)
for artifact selection, JSON output, registry pinning, and cache management.
Return to the [Datamonger overview](index.md).
