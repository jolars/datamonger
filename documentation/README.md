# Datamonger documentation

Diplodocus builds the site at <https://datamonger.dev/> from the authored pages
in `pages/` and the Python and R package sources. The site includes API
references and nine shared concepts. Julia and the CLI have authored guides.
The short guides link to the package READMEs for more detail. The build does
not execute examples or download datasets.

## Local preview

With Datamonger and Diplodocus checked out beside each other, build Diplodocus
with Rust 1.98.0. Then run these commands from the Datamonger repository root:

```console
../diplodocus/target/debug/diplodocus check --config documentation/diplodocus.toml
../diplodocus/target/debug/diplodocus serve --config documentation/diplodocus.toml --output documentation/site --port 8001 --live-reload
```

Open <http://127.0.0.1:8001/>. To generate deployable files without serving
them, replace `serve` with `build` and omit `--port 8001 --live-reload`.
Generated snapshots, site files, and npm dependencies are ignored by Git.
The R extractor currently reports nonfatal documentation warnings during a
successful check.

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
