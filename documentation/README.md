# Datamonger documentation

Diplodocus builds the site at <https://datamonger.dev/> from authored guides,
Python, R, and Julia API sources, and R package documents. Nine concepts connect
equivalent operations across all three language clients.
See [the dogfooding assessment](assessment.md) for coverage and known limits.

## Local preview

With Datamonger and Diplodocus checked out beside each other, build the pinned
Diplodocus revision `4f6efd87895e0f586e90589cd7d3c6c0d8cb0734` in its devenv shell:

```console
cd ../diplodocus
devenv shell -- cargo build --locked --bin diplodocus
cd ../datamonger
```

Enter Datamonger's `devenv shell` for Python, R, Julia, and the package dependencies.
The shell prepares the Python environment. Instantiate the Julia project and
compile the R client's native extension before the first build or after changing
its dependencies or C code:

```console
mkdir -p /tmp/datamonger-docs-library
julia tools/dm_julia_core.jl
julia --project=packages/julia -e 'using Pkg; Pkg.instantiate()'
R CMD INSTALL --library=/tmp/datamonger-docs-library packages/r
../diplodocus/target/debug/diplodocus serve --config documentation/diplodocus.toml --output documentation/site --port 8001 --live-reload
```

Open <http://127.0.0.1:8001/>. To generate deployable files, replace `serve` with
`build` and omit `--port 8001 --live-reload`. Generated snapshots, site files,
and npm dependencies are ignored by Git. `build` and `serve` validate sources,
complete Julia's generated error types through the prepared runtime, execute
Python and Julia API doctests, and use native R for package documents and examples.
`check` remains static and reports 15 unresolved generated Julia types for this
workspace; use `build` for complete validation.

After building, run `python tools/dm_docs.py` from the repository root to install
the favicon files and shared HTML head markup. The script copies
`documentation/public/` into the published root, `documentation/site/`, and
adds `documentation/head.html` to every generated HTML page. CI runs this step
before deployment. For local previews, rerun it after Diplodocus rebuilds the
site. Keep favicon markup in the shared file so all pages use the same links.

The [offline conformance walkthrough](../packages/r/vignettes/offline-conformance.Rmd)
retrieves a bundled CSV from a private temporary cache, verifies its decoded
values and canonical digest, and renders tables and a plot. Every retrieval
uses `offline = TRUE`; building the article makes no network requests. The
README and authored Markdown guide examples remain illustrative.

The R package includes the shared conformance corpus and its test registry, so
the article also runs from an installed package. `R CMD build packages/r`
renders the standard R vignette with knitr, rmarkdown, and Pandoc, which are
included in the repository's devenv environment. Diplodocus executes the same
source with its native knitr collector.

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

## Publishing

The [Documentation workflow](../.github/workflows/documentation.yml) builds with
a pinned Diplodocus commit and checks the Cloudflare package on pull requests.
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
