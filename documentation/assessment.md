# Diplodocus dogfooding assessment

The current configuration extracts Python, R, and Julia APIs and connects nine
equivalent operations across all three clients. The Rust CLI has an authored guide
because Diplodocus has no Rust API extractor.

The documentation workflow and [preview instructions](README.md) use one pinned
Diplodocus revision and prepare the language clients before extraction. `build`
performs source validation, runtime-assisted Julia completion, and example
execution. `check` remains static and reports 15 unresolved Julia types generated
by `@define_error`; that result does not describe the complete build's coverage.

## Package coverage

| Client | Extracted coverage | Practical result |
|:-------|:-------------------|:-----------------|
| Python | All 20 root `__all__` exports resolve. The snapshot contains 98 items, including 49 fields and the `DatasetData` type alias. | Public reexport names appear in headings, navigation, and search. `fetch_data` has one page containing all three overload signatures and its implementation prose. |
| R | All 11 NAMESPACE exports, eight registered S3 methods, and one package topic have documentation. | Shared Rd topics retain usages, arguments, and return descriptions. All eight methods share three maintained help topics. The package also has an overview, authors, citation, license, community page, and executable vignette. |
| Julia | All 42 exported bindings resolve. The snapshot contains 126 items, including the 15 generated exception types. | Runtime completion verifies the supplied checkout and records its observations separately from static source facts. Function pages combine the overview and method documentation. |
| Rust CLI | No API extraction. | The authored guide covers building, listing, inspection, and artifact export and links to the complete package README. |

These counts describe extraction, not independent documentation quality. Some
Julia fields and generated error types still have no explanatory source prose.

## Resolved compatibility and content gaps

- Python overloads share a callable page and search result. Stable signature
  anchors retain references to individual overloads.
- Public Python reexports supply display names, while snapshots retain the
  implementation names and source locations.
- `DatasetData` retains its annotated type-alias definition and signature links.
- All 48 public Python dataclass fields, the `bytes_removed` property, and
  `BUNDLED_REGISTRY` retain their source descriptions.
- Maintained R help topics cover all eight registered S3 methods.
- The authored R community page replaces the automatically discovered contributor
  guide before parsing. The unused guide emits no list-syntax warnings.
- Automatically discovered package documents can link to existing repository
  files and directories outside the declared site content.
- Julia's macro-generated error types complete through the prepared runtime.
  Equivalent API links now reach Julia overviews containing method prose.

Small Diplodocus fixtures cover these behaviors without requiring this sibling
checkout.

## Executed offline examples

The Python and Julia `cache_info` API doctests inspect fresh temporary directories
and verify that the empty cache has zero entries and zero bytes. The Python
standard library runner checks its transcript's expected output. Julia's native
adapter checks the REPL transcript, including its multiline temporary-directory
block. Both run during extraction, use the supplied checkout, retain outcomes and
runtime observations, make no network requests, and leave the user's cache alone.

The [R offline conformance walkthrough](../packages/r/vignettes/offline-conformance.Rmd)
retrieves the bundled mixed CSV through `fetch_artifact()` and `fetch_data()`. It
seeds a private temporary cache, requires `offline = TRUE`, checks the five rows
and four typed columns against their expected values, and verifies the canonical
digest from the shared corpus. The article renders the values, reproducibility
metadata, and a PNG plot, then removes its cache.

Ordinary Markdown fences in the README and authored guides remain illustrative.
They include installation commands and retrievals that can access the network.
The executable API examples use explicit doctest syntax instead.

## Validation

An isolated build in Datamonger's prepared environment produces 211 HTML pages.
The generated site has no missing local links, assets, or heading anchors. Browser
checks at widths of 1440 and 390 pixels verify successful responses, one title,
no viewport overflow, and no JavaScript errors. Search returns one Python
`fetch_data` result with all three overloads and links to the equivalent R and
Julia operations. Representative desktop and mobile screenshots cover the Python
reference, Julia function and error pages, and the R article.

Generation from a relocated snapshot after removing its source checkout produces
byte-identical site files. The build's remaining R diagnostics concern file-level
Rd attribution, not missing package prose.

The source validation and browser checks cover local generation. Publishing uses
the pinned workflow after the corresponding Diplodocus revision is available on
GitHub.
