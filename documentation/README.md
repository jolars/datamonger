# Diplodocus prototype

This directory prototypes one documentation site for Datamonger's Python, R,
Julia, and command-line clients. The working configuration uses authored
Markdown. It does not execute examples or download data.

## Preview

With the Datamonger and Diplodocus repositories checked out beside each other,
run these commands from the **Diplodocus repository**:

```console
devenv shell -- cargo build --locked
devenv shell -- target/debug/diplodocus check --config ../datamonger/documentation/diplodocus.toml
devenv shell -- target/debug/diplodocus serve --config ../datamonger/documentation/diplodocus.toml --output ../datamonger/documentation/site --port 8001 --live-reload
```

Open <http://127.0.0.1:8001/>. Edits to `pages/` rebuild the preview. For a static
build, replace `serve` with `build` and omit `--port 8001 --live-reload`.
Generated snapshots and site files are ignored by `documentation/.gitignore`.
No installation of the Datamonger clients is needed to build this site.

The short guides are prototype content. The package READMEs remain the complete
client guides; consolidate them before adopting this site as the main manual.
`documentation/` is used because the repository ignores `docs/` for pkgdown.

## API extraction compatibility

`diplodocus-api.toml` is an experimental configuration that adds static Python
and R extraction and nine links between equivalent operations. It currently
fails validation. Reproduce the diagnostics from the Diplodocus repository:

```console
devenv shell -- target/debug/diplodocus check --config ../datamonger/documentation/diplodocus-api.toml
```

The initial check found these compatibility gaps:

- Python context-manager decorators produce `python-unsupported-surface`
  errors, including on private helpers. A signature expression in
  `_canonical.py` also produces `python-unsupported-syntax`.
- R's `useDynLib(datamonger, .registration = TRUE, .fixes = "C_")`
  produces `r-unsupported-namespace`. Public definitions and their Rd usage
  entries are unresolved, producing further errors and preventing concept
  links from resolving. The namespace error may contribute to these failures;
  investigate the definition errors again after it is fixed.
- The R package-level Rd topic has no maintained declaration target, and
  `\docType` produces an unsupported-markup warning.
- Julia and Rust API extraction are not supported by Diplodocus. Their guides
  are authored pages in both configurations.

These diagnostics are preserved through the experimental configuration rather
than changing client source code to fit the extractor. The default configuration
declares only authored content and passes `check`; it does not claim to provide
generated API documentation. Before enabling extraction, add regression
fixtures in Diplodocus for these source patterns and address each diagnostic.
