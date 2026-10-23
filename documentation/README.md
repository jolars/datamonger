# Datamonger documentation

Diplodocus builds the site at <https://datamonger.dev/> from authored guides,
Python, R, and Julia API sources, and R package documents. Nine concepts connect
equivalent operations across all three language clients.
See [the dogfooding assessment](assessment.md) for coverage and known limits.

The [CLI reference](pages/cli-reference.md) is generated from the CLI's clap
definitions with clapdown and committed with the authored guides. Regenerate it
with `cargo run --locked --manifest-path packages/cli/Cargo.toml --example generate_cli_docs`
after changing commands or help text. CI checks that the reference is current.

## Local preview

Enter Datamonger's `devenv shell` for the locked Diplodocus CLI, Python, R,
Julia, and the package dependencies. Update Diplodocus with
`devenv update diplodocus`. To test a neighboring checkout instead, enter:

```console
devenv --override-input diplodocus path:../diplodocus shell
```

The shell prepares the Python environment. Instantiate the Julia project and
compile the R client's native extension before the first build or after changing
its dependencies or C code:

```console
mkdir -p /tmp/datamonger-docs-library
julia tools/dm_julia_core.jl
julia --project=packages/julia -e 'using Pkg; Pkg.instantiate()'
R CMD INSTALL --library=/tmp/datamonger-docs-library packages/r
python tools/dm_catalog.py
diplodocus build --config documentation/diplodocus.yaml --output documentation/site
npm ci --ignore-scripts --prefix documentation
python tools/dm_docs.py --serve --port 8001
```

Open <http://127.0.0.1:8001/>. The preview serves the completed files with the
same clean page URLs as the deployed site. Diplodocus's built-in `serve` uses
an in-memory site and cannot include assets installed after rendering.
Generated snapshots, site files, and npm dependencies are ignored by Git.
`build` and `serve` validate sources,
complete Julia's generated error types through the prepared runtime, execute
Python and Julia API doctests, and use native R for package documents and examples.
`check` remains static and reports 15 unresolved generated Julia types for this
workspace; use `build` for complete validation.

Run `npm ci --ignore-scripts --prefix documentation` once to install the pinned
website dependencies. After building, run `python tools/dm_docs.py` from the
repository root to install public assets, catalog metadata, MiniSearch, shared
HTML head markup, and the Datasets navigation link. CI runs these steps before
deployment. For local previews, rerun the script after Diplodocus rebuilds the
site. Keep shared head markup in `documentation/head.html`.

The R [getting started vignette](../packages/r/vignettes/introduction.Rmd)
introduces dataset discovery, retrieval, citations, reproducibility, and caching.
Metadata examples use the bundled registry with `offline = TRUE`. Download
examples and the code that depends on them use `eval = FALSE`, so building the
article makes no network requests. The README and authored Markdown guide
examples remain illustrative.

`R CMD build packages/r` renders the standard R vignette with knitr, rmarkdown,
and Pandoc, which are included in the repository's devenv environment.
Diplodocus executes the same source with its native knitr collector.

The Julia package's [offline data workflow](../packages/julia/tutorials/offline-workflow.md)
and [reproducibility guide](../packages/julia/tutorials/reproducibility.md) are
mounted under its `tutorials/` section by the `julia-tutorials` content collection.
They use the existing Diplodocus build and the shared API reference. Their Julia
fences remain illustrative during site builds; the offline walkthrough can be
run in order from a prepared repository checkout.

The Python and Julia `cache_info` doctests inspect fresh temporary directories
and verify that an empty cache has no entries or bytes. They make no network
requests and leave the user's cache untouched. API doctest failures prevent
publication. Ordinary Markdown fences in the README and guides remain
illustrative.

## Dataset catalog

`python tools/dm_catalog.py` generates the browser, dataset version pages, and
JSON metadata in the ignored `documentation/generated/datasets/` directory.
Generate it before building the site. The generator reads the clients' bundled
selector in `packages/cli/assets/selector.json`, verifies the checked-in index
against its digest and schemas, and makes no network requests. The catalog
follows client registry updates rather than pending registry release PRs.
Use `--selector PATH` to preview another checked-in snapshot.

Diplodocus renders the generated Markdown under `/datasets/`, including a
complete table of default dataset versions that works without JavaScript.
The browser loads a compact JSON projection and self-hosted MiniSearch only
when visitors open the catalog. Filters and sorting persist in the query
string. Numeric filters must match the same task and split; missing task
metadata does not imply unsupervised learning. Detail pages include pinned
retrieval examples, metadata, and links to other versions in the selected
registry. Long component lists are summarized in HTML and remain complete in
each downloadable JSON record.

Generated catalog files are never edited manually. The generator removes only
stale files listed in its previous output inventory. No dataset artifact is
downloaded or included in the website.

Generator regression tests run as part of `devenv test`. After building the
site, run the browser tests with:

```console
cd documentation
npx --no-install playwright install chromium
npm run test:catalog
```

The tests start a preview automatically. To use a system Chromium on NixOS, set
`DM_CHROMIUM_PATH` to its executable. Set `DM_DOCS_TEST_URL` to test an already
running local preview. CI runs the browser tests before checking the Worker
package and deploying the site.

## Publishing

The [Documentation workflow](../.github/workflows/documentation.yml) builds with
a pinned setup action and CLI release and checks the Cloudflare package on pull
requests.
Each push to `main` deploys the generated files as Worker static assets to
`datamonger.dev`. A manual workflow dispatch from `main` can retry a failed
deployment. The site requires no running Datamonger client or dataset source.

Set these GitHub repository secrets before the first deployment:

- `CLOUDFLARE_ACCOUNT_ID`: the ID of the Cloudflare account containing the
  `datamonger.dev` zone.
- `CLOUDFLARE_API_TOKEN`: an API token with Workers Editor access in that
  account and Workers Routes Write access to the `datamonger.dev` zone.

Cloudflare creates the DNS record and certificate when the Worker custom domain
is attached. The zone must be active in the selected account, and the hostname
must not have a conflicting CNAME record. See Cloudflare's [custom domain
guide](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)
and [Worker permissions](https://developers.cloudflare.com/workers/authorization/workers/).

To validate a local static build with the pinned Wrangler version, run:

```console
cd documentation
npm ci --ignore-scripts
npx --no-install wrangler deploy --dry-run
```

`documentation/` is used because the repository ignores `docs/` for pkgdown.
