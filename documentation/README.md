# Datamonger documentation

Diplodocus builds the site at <https://datamonger.dev/> from authored guides,
Python and R API sources, and R package documents. Julia has a package overview
and guide. Nine concepts connect equivalent Python and R operations.
See [the dogfooding assessment](assessment.md) for coverage and known limits.

## Local preview

With Datamonger and Diplodocus checked out beside each other, build the pinned
Diplodocus revision `dd35393d258f8192b66c66564fd0ff10f1e048e7` in its devenv shell:

```console
cd ../diplodocus
devenv shell -- cargo build --locked --bin diplodocus
cd ../datamonger
```

Enter Datamonger's `devenv shell` for R and the package dependencies. Compile the
R client's native extension before the first build or after changing its C code:

```console
mkdir -p /tmp/datamonger-docs-library
R CMD INSTALL --library=/tmp/datamonger-docs-library packages/r
../diplodocus/target/debug/diplodocus check --config documentation/diplodocus.toml
../diplodocus/target/debug/diplodocus serve --config documentation/diplodocus.toml --output documentation/site --port 8001 --live-reload
```

Open <http://127.0.0.1:8001/>. To generate deployable files, replace `serve` with
`build` and omit `--port 8001 --live-reload`. Generated snapshots, site files,
and npm dependencies are ignored by Git. `check` does not execute examples.
`build` and `serve` use native R for authors, citations, and executable package
documentation. The [offline conformance walkthrough](../packages/r/vignettes/offline-conformance.Rmd)
retrieves a bundled CSV from a private temporary cache, verifies its decoded
values and canonical digest, and renders tables and a plot. Every retrieval
uses `offline = TRUE`; building the article makes no network requests. The
README and authored Markdown guide examples remain illustrative.

The R package includes the shared conformance corpus and its test registry, so
the article also runs from an installed package. `R CMD build packages/r`
renders the standard R vignette with knitr, rmarkdown, and Pandoc, which are
included in the repository's devenv environment. Diplodocus executes the same
source with its native knitr collector.

The published configuration intentionally disables Julia API extraction because
15 exported macro-generated error types cannot be resolved statically. The
assessment records how to enable extraction in this configuration to reproduce
the failure; there is no separate API configuration.

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
