# Command-line reference

Verified research dataset artifacts

**Usage:** `datamonger [OPTIONS] <COMMAND>`

## Options

- **`--selector <SELECTOR>`**

  Read a registry selector from this file instead of discovering a project selector

- **`--cache-dir <CACHE_DIR>`**

  Use this directory for the CLI's private cache

- **`--offline`**

  Use only bundled or cached registry indexes and cached artifacts

- **`--json`**

  Print structured JSON results and report errors as JSON on stderr

## `datamonger list`

List datasets in the selected registry

**Usage:** `datamonger list [OPTIONS]`

### Options

- **`--source <SOURCE>`**

  Include only datasets from this source, such as uci or libsvm

## `datamonger info`

Show a dataset's metadata, provenance, and registered artifacts

**Usage:** `datamonger info <DATASET>`

### Arguments

- **`<DATASET>`**

  Dataset identifier in SOURCE:NAME or SOURCE:NAME@VERSION form

## `datamonger fetch`

Download artifacts and verify their registered sizes and SHA-256 hashes.

Fetches every artifact unless --artifact selects one. Files stay in the private cache unless --output-dir also exports them. Registered compression is preserved; datasets are not decoded or checked for canonical logical values.

**Usage:** `datamonger fetch [OPTIONS] <DATASET>`

### Arguments

- **`<DATASET>`**

  Dataset identifier in SOURCE:NAME or SOURCE:NAME@VERSION form

### Options

- **`--artifact <ARTIFACT>`**

  Fetch only the named artifact, such as train or test

- **`--output-dir <OUTPUT_DIR>`**

  Also export verified bytes under SOURCE/NAME/VERSION/ARTIFACT.FORMAT.

  Compressed artifacts retain their compression suffix. Existing exports are never overwritten.

## `datamonger registry`

Inspect the selected registry or resolve a release through an HTTPS catalog

**Usage:** `datamonger registry <COMMAND>`

### `datamonger registry show`

Show the active registry selector without downloading its index

**Usage:** `datamonger registry show`

### `datamonger registry resolve`

Resolve a release to a selector with a fixed index SHA-256.

Requires network access. Prints the selector as JSON and optionally writes it to a file. A checksum fixes the index bytes but does not authenticate the catalog's publisher.

**Usage:** `datamonger registry resolve [OPTIONS] <RELEASE>`

#### Arguments

- **`<RELEASE>`**

  Registry release to resolve, such as 1.1.0

#### Options

- **`--catalog-url <CATALOG_URL>`**

  HTTPS catalog from which to resolve the release

  Default value: `https://raw.githubusercontent.com/jolars/datamonger/main/registry/catalog.json`

- **`--output <OUTPUT>`**

  Also write the selector to this file, such as .datamonger/selector.json

## `datamonger cache`

Inspect or clean the CLI's private cache

**Usage:** `datamonger cache <COMMAND>`

### `datamonger cache list`

List cached registries and artifacts, including their sizes and integrity

**Usage:** `datamonger cache list`

### `datamonger cache clean`

Remove cached objects, skipping any objects currently in use.

Requires either --dataset or --all. Dataset cleanup removes artifacts associated with the exact version in a bundled or cached registry.

**Usage:** `datamonger cache clean [OPTIONS]`

#### Options

- **`--dataset <DATASET>`**

  Remove artifacts for a dataset in SOURCE:NAME@VERSION form

- **`--all`**

  Remove all cached registry indexes and artifacts
