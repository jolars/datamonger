use std::path::PathBuf;

use clap::{Parser, Subcommand};

const CATALOG_URL: &str =
    "https://raw.githubusercontent.com/jolars/datamonger/main/registry/catalog.json";

#[derive(Parser)]
#[command(
    name = "datamonger",
    version,
    about = "Verified research dataset artifacts"
)]
pub(crate) struct Cli {
    /// Read a registry selector from this file instead of discovering a project selector.
    #[arg(long, global = true)]
    pub(crate) selector: Option<PathBuf>,
    /// Use this directory for the CLI's private cache.
    #[arg(long, global = true)]
    pub(crate) cache_dir: Option<PathBuf>,
    /// Use only bundled or cached registry indexes and cached artifacts.
    #[arg(long, global = true)]
    pub(crate) offline: bool,
    /// Print structured JSON results and report errors as JSON on stderr.
    #[arg(long, global = true)]
    pub(crate) json: bool,
    #[command(subcommand)]
    pub(crate) command: Command,
}

#[derive(Subcommand)]
pub(crate) enum Command {
    /// List datasets in the selected registry.
    List {
        /// Include only datasets from this source, such as uci or libsvm.
        #[arg(long)]
        source: Option<String>,
    },
    /// Show a dataset's metadata, provenance, and registered artifacts.
    Info {
        /// Dataset identifier in SOURCE:NAME or SOURCE:NAME@VERSION form.
        dataset: String,
    },
    /// Download artifacts and verify their registered sizes and SHA-256 hashes.
    ///
    /// Fetches every artifact unless --artifact selects one. Files stay in the
    /// private cache unless --output-dir also exports them. Registered compression
    /// is preserved; datasets are not decoded or checked for canonical logical values.
    Fetch {
        /// Dataset identifier in SOURCE:NAME or SOURCE:NAME@VERSION form.
        dataset: String,
        /// Fetch only the named artifact, such as train or test.
        #[arg(long)]
        artifact: Option<String>,
        /// Also export verified bytes under SOURCE/NAME/VERSION/ARTIFACT.FORMAT.
        ///
        /// Compressed artifacts retain their compression suffix. Existing exports
        /// are never overwritten.
        #[arg(long)]
        output_dir: Option<PathBuf>,
    },
    /// Inspect the selected registry or resolve a release through an HTTPS catalog.
    Registry {
        #[command(subcommand)]
        action: RegistryCommand,
    },
    /// Inspect or clean the CLI's private cache.
    Cache {
        #[command(subcommand)]
        action: CacheCommand,
    },
}

#[derive(Subcommand)]
pub(crate) enum RegistryCommand {
    /// Show the active registry selector without downloading its index.
    Show,
    /// Resolve a release to a selector with a fixed index SHA-256.
    ///
    /// Requires network access. Prints the selector as JSON and optionally writes
    /// it to a file. A checksum fixes the index bytes but does not authenticate
    /// the catalog's publisher.
    Resolve {
        /// Registry release to resolve, such as 1.1.0.
        release: String,
        /// HTTPS catalog from which to resolve the release.
        #[arg(long, default_value = CATALOG_URL)]
        catalog_url: String,
        /// Also write the selector to this file, such as .datamonger/selector.json.
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

#[derive(Subcommand)]
pub(crate) enum CacheCommand {
    /// List cached registries and artifacts, including their sizes and integrity.
    List,
    /// Remove cached objects, skipping any objects currently in use.
    ///
    /// Requires either --dataset or --all. Dataset cleanup removes artifacts
    /// associated with the exact version in a bundled or cached registry.
    Clean {
        /// Remove artifacts for a dataset in SOURCE:NAME@VERSION form.
        #[arg(long, conflicts_with = "all")]
        dataset: Option<String>,
        /// Remove all cached registry indexes and artifacts.
        #[arg(long)]
        all: bool,
    },
}
