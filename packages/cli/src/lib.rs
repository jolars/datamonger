mod cache;
mod error;
mod http;
mod registry;

use std::collections::BTreeMap;
use std::fs;
use std::io::{Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

use clap::{Parser, Subcommand};
use serde_json::{Value, json};
use tempfile::NamedTempFile;

use crate::cache::{CachedFile, default_root};
use crate::error::{Error, Result};
use crate::http::HttpClient;
use crate::registry::{Index, Selector, active_selector, dataset_id, parse_catalog, parse_index};

const CATALOG_URL: &str =
    "https://raw.githubusercontent.com/jolars/datamonger/main/registry/catalog.json";

#[derive(Parser)]
#[command(
    name = "datamonger",
    version,
    about = "Verified research dataset artifacts"
)]
struct Cli {
    #[arg(long, global = true)]
    selector: Option<PathBuf>,
    #[arg(long, global = true)]
    cache_dir: Option<PathBuf>,
    #[arg(long, global = true)]
    offline: bool,
    #[arg(long, global = true)]
    json: bool,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    List {
        #[arg(long)]
        source: Option<String>,
    },
    Info {
        dataset: String,
    },
    Fetch {
        dataset: String,
        #[arg(long)]
        artifact: Option<String>,
        #[arg(long)]
        output_dir: Option<PathBuf>,
    },
    Registry {
        #[command(subcommand)]
        action: RegistryCommand,
    },
    Cache {
        #[command(subcommand)]
        action: CacheCommand,
    },
}

#[derive(Subcommand)]
enum RegistryCommand {
    Show,
    Resolve {
        release: String,
        #[arg(long, default_value = CATALOG_URL)]
        catalog_url: String,
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

#[derive(Subcommand)]
enum CacheCommand {
    List,
    Clean {
        #[arg(long, conflicts_with = "all")]
        dataset: Option<String>,
        #[arg(long)]
        all: bool,
    },
}

pub fn run() -> i32 {
    let cli = Cli::parse();
    match execute(&cli) {
        Ok(()) => 0,
        Err(error) => {
            if cli.json {
                let value =
                    json!({"error": {"category": error.category, "message": error.message}});
                eprintln!(
                    "{}",
                    serde_json::to_string(&value).expect("error serializes")
                );
            } else {
                eprintln!("error[{}]: {}", error.category, error.message);
            }
            1
        }
    }
}

fn execute(cli: &Cli) -> Result<()> {
    let cache_root = match &cli.cache_dir {
        Some(path) => path.clone(),
        None => default_root()?,
    };
    match &cli.command {
        Command::Cache { action } => match action {
            CacheCommand::List => {
                let inventory = cache::inventory(&cache_root)?;
                if cli.json {
                    print_json(&inventory)?;
                } else {
                    println!(
                        "Cache: {} ({} bytes)",
                        inventory.location.display(),
                        inventory.total_size
                    );
                    for entry in inventory.entries {
                        println!(
                            "{} {} {} bytes {}",
                            entry.kind,
                            entry.sha256,
                            entry.size,
                            if entry.valid { "valid" } else { "INVALID" }
                        );
                    }
                }
                Ok(())
            }
            CacheCommand::Clean { dataset, all } => {
                if let Some(id) = dataset {
                    let (_, _, version) = registry::split_id(id)?;
                    if version.is_none() {
                        return Err(Error::new(
                            "cache",
                            "--dataset requires SOURCE:NAME@VERSION",
                        ));
                    }
                }
                let result = cache::clean(&cache_root, dataset.as_deref(), *all)?;
                if cli.json {
                    print_json(&result)?;
                } else {
                    println!(
                        "Removed {} bytes in {} objects; skipped {} active objects",
                        result.bytes_removed,
                        result.removed.len(),
                        result.skipped.len()
                    );
                }
                Ok(())
            }
        },
        Command::Registry { action } => match action {
            RegistryCommand::Show => {
                let selector = selected_selector(cli)?;
                if cli.json {
                    print_json(&selector)?;
                } else {
                    println!(
                        "{} {} {}",
                        selector.release, selector.index_sha256, selector.index_url
                    );
                }
                Ok(())
            }
            RegistryCommand::Resolve {
                release,
                catalog_url,
                output,
            } => {
                if cli.offline {
                    return Err(Error::new(
                        "unsupported-registry",
                        "registry resolve requires network access",
                    ));
                }
                if !catalog_url.starts_with("https://") {
                    return Err(Error::new(
                        "unsupported-registry",
                        "catalog URL must use HTTPS",
                    ));
                }
                let bytes = HttpClient::new()?.get_bytes(catalog_url, true)?;
                let selector = parse_catalog(&bytes, release)?;
                if let Some(path) = output {
                    write_selector(path, &selector)?;
                }
                print_json(&selector)
            }
        },
        Command::List { source } => {
            let selector = selected_selector(cli)?;
            let index = load_index(&selector, &cache_root, cli.offline)?;
            let datasets: Vec<Value> = index
                .datasets()
                .iter()
                .filter(|entry| source.as_deref().is_none_or(|name| entry["source"] == name))
                .map(|entry| {
                    json!({
                        "dataset_id": dataset_id(entry),
                        "title": entry["title"],
                        "modality": entry["modality"],
                        "artifacts": entry["artifacts"].as_array().expect("validated artifacts")
                            .iter().map(|artifact| artifact["name"].clone()).collect::<Vec<_>>()
                    })
                })
                .collect();
            if cli.json {
                print_json(&json!({"registry": index.selector, "datasets": datasets}))?;
            } else {
                for entry in datasets {
                    println!(
                        "{}\t{}",
                        entry["dataset_id"].as_str().unwrap_or(""),
                        entry["title"].as_str().unwrap_or("")
                    );
                }
            }
            Ok(())
        }
        Command::Info { dataset } => {
            let selector = selected_selector(cli)?;
            let index = load_index(&selector, &cache_root, cli.offline)?;
            let entry = index.resolve(dataset)?;
            if cli.json {
                print_json(&json!({
                    "dataset_id": dataset_id(entry),
                    "registry": index.selector,
                    "dataset": entry,
                }))?;
            } else {
                println!(
                    "{} — {}",
                    dataset_id(entry),
                    entry["title"].as_str().unwrap_or("")
                );
                println!(
                    "Registry: {} {}",
                    index.selector.release, index.selector.index_sha256
                );
                println!("{}", entry["description"].as_str().unwrap_or(""));
                let provenance = &entry["provenance"];
                println!(
                    "Provider: {}",
                    provenance["provider"].as_str().unwrap_or("")
                );
                println!(
                    "Source: {}",
                    provenance["landing_page"].as_str().unwrap_or("")
                );
                let license = &entry["license"];
                println!(
                    "License: {} ({})",
                    license["identifier"].as_str().unwrap_or("unspecified"),
                    license["status"].as_str().unwrap_or("unknown")
                );
                for artifact in entry["artifacts"].as_array().expect("validated artifacts") {
                    println!(
                        "Artifact: {} ({}, {}, {} bytes)",
                        artifact["name"].as_str().unwrap_or(""),
                        artifact["format"].as_str().unwrap_or(""),
                        artifact["compression"].as_str().unwrap_or(""),
                        artifact["size"].as_u64().unwrap_or(0)
                    );
                    println!("  SHA-256: {}", artifact["sha256"].as_str().unwrap_or(""));
                    println!(
                        "  Distribution: {}",
                        artifact["distribution"].as_str().unwrap_or("")
                    );
                    if let Some(preservation) = artifact["preservation"].as_str() {
                        println!("  Preservation: {preservation}");
                    }
                    for location in artifact["downloads"]
                        .as_array()
                        .expect("validated downloads")
                    {
                        println!("  Download: {}", location["url"].as_str().unwrap_or(""));
                    }
                }
                println!("Verification on fetch: artifact bytes only");
            }
            Ok(())
        }
        Command::Fetch {
            dataset,
            artifact,
            output_dir,
        } => {
            let selector = selected_selector(cli)?;
            let index = load_index(&selector, &cache_root, cli.offline)?;
            fetch(
                cli,
                &index,
                dataset,
                artifact.as_deref(),
                output_dir.as_deref(),
                &cache_root,
            )
        }
    }
}

fn selected_selector(cli: &Cli) -> Result<Selector> {
    let cwd = std::env::current_dir()
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    active_selector(cli.selector.as_deref(), &cwd)
}

fn load_index(selector: &Selector, root: &Path, offline: bool) -> Result<Index> {
    let bytes = if selector.is_bundled() {
        registry::BUNDLED_INDEX.to_vec()
    } else {
        let client = if offline {
            None
        } else {
            Some(HttpClient::new()?)
        };
        let cached = cache::get_or_fetch(
            root,
            "registries",
            &selector.index_sha256,
            None,
            "unsupported-registry",
            offline,
            |temporary| {
                client.as_ref().expect("online client exists").download(
                    &selector.index_url,
                    false,
                    temporary.as_file_mut(),
                )
            },
        )?;
        cache::read_cached(&cached)?
    };
    parse_index(&bytes, selector.clone())
}

struct FetchedArtifact {
    name: String,
    digest: String,
    size: u64,
    format: String,
    compression: String,
    cached: CachedFile,
    output_path: Option<PathBuf>,
}

fn fetch(
    cli: &Cli,
    index: &Index,
    id: &str,
    chosen: Option<&str>,
    output_dir: Option<&Path>,
    root: &Path,
) -> Result<()> {
    let dataset = index.resolve(id)?;
    let artifacts = dataset["artifacts"]
        .as_array()
        .expect("validated artifacts");
    let selected: Vec<&Value> = match chosen {
        Some(name) => artifacts
            .iter()
            .filter(|artifact| artifact["name"] == name)
            .collect(),
        None => artifacts.iter().collect(),
    };
    if selected.is_empty() {
        let names = artifacts
            .iter()
            .filter_map(|artifact| artifact["name"].as_str())
            .collect::<Vec<_>>()
            .join(", ");
        return Err(Error::new(
            "artifact-selection",
            format!("unknown artifact; available: {names}"),
        ));
    }
    if selected
        .iter()
        .any(|artifact| artifact["distribution"] == "metadata-only")
    {
        return Err(Error::new(
            "artifact-unavailable",
            "metadata-only artifact cannot be fetched",
        ));
    }
    let paths: Vec<Option<PathBuf>> = selected
        .iter()
        .map(|artifact| output_dir.map(|dir| output_path(dir, dataset, artifact)))
        .collect();
    for path in paths.iter().flatten() {
        if path.exists() {
            return Err(Error::new(
                "cache",
                format!("output already exists: {}", path.display()),
            ));
        }
    }
    let client = if cli.offline {
        None
    } else {
        Some(HttpClient::new()?)
    };
    let mut fetched = Vec::new();
    for (artifact, path) in selected.iter().zip(paths) {
        let name = artifact["name"].as_str().expect("validated name");
        let digest = artifact["sha256"].as_str().expect("validated digest");
        let size = artifact["size"].as_u64().expect("validated size");
        let downloads = artifact["downloads"]
            .as_array()
            .expect("validated downloads");
        let cached = cache::get_or_fetch(
            root,
            "objects",
            digest,
            Some(size),
            "artifact-integrity",
            cli.offline,
            |temporary| {
                let mut failures = Vec::new();
                let mut integrity_failure = false;
                for download in downloads {
                    temporary
                        .as_file_mut()
                        .set_len(0)
                        .map_err(|error| Error::new("cache", error.to_string()))?;
                    temporary
                        .as_file_mut()
                        .seek(SeekFrom::Start(0))
                        .map_err(|error| Error::new("cache", error.to_string()))?;
                    let url = download["url"].as_str().expect("validated URL");
                    match client.as_ref().expect("online client exists").download(
                        url,
                        false,
                        temporary.as_file_mut(),
                    ) {
                        Ok(()) => {
                            if cache::verify_path(temporary.path(), digest, size)? {
                                return Ok(());
                            }
                            integrity_failure = true;
                            failures.push(format!("{url}: size or SHA-256 mismatch"));
                        }
                        Err(error) => failures.push(format!("{url}: {error}")),
                    }
                }
                Err(Error::new(
                    if integrity_failure {
                        "artifact-integrity"
                    } else {
                        "retrieval-exhausted"
                    },
                    format!("all retrieval locations failed: {}", failures.join("; ")),
                ))
            },
        )?;
        fetched.push(FetchedArtifact {
            name: name.to_owned(),
            digest: digest.to_owned(),
            size,
            format: artifact["format"]
                .as_str()
                .expect("validated format")
                .to_owned(),
            compression: artifact["compression"]
                .as_str()
                .expect("validated compression")
                .to_owned(),
            cached,
            output_path: path,
        });
    }
    let mut created = Vec::new();
    for artifact in &fetched {
        if let Some(path) = &artifact.output_path {
            if let Err(error) =
                cache::copy_verified(&artifact.cached, path, &artifact.digest, artifact.size)
            {
                for path in created {
                    let _ = fs::remove_file(path);
                }
                return Err(error);
            }
            created.push(path.clone());
        }
    }
    let results: Vec<Value> = fetched
        .iter()
        .map(|artifact| {
            json!({
                "name": artifact.name,
                "sha256": artifact.digest,
                "size": artifact.size,
                "format": artifact.format,
                "compression": artifact.compression,
                "cache_path": artifact.cached.path,
                "output_path": artifact.output_path,
            })
        })
        .collect();
    let report = json!({
        "dataset_id": dataset_id(dataset),
        "registry": index.selector,
        "verification": "artifact",
        "artifacts": results,
    });
    if cli.json {
        print_json(&report)?;
    } else {
        println!("{} — artifact verified", dataset_id(dataset));
        println!(
            "Registry: {} {}",
            index.selector.release, index.selector.index_sha256
        );
        for artifact in &fetched {
            println!("{}\t{}", artifact.name, artifact.cached.path.display());
            if let Some(path) = &artifact.output_path {
                println!("  exported: {}", path.display());
            }
        }
    }
    Ok(())
}

fn output_path(root: &Path, dataset: &Value, artifact: &Value) -> PathBuf {
    let mut extension = artifact["format"]
        .as_str()
        .expect("validated format")
        .to_owned();
    match artifact["compression"]
        .as_str()
        .expect("validated compression")
    {
        "gzip" => extension.push_str(".gz"),
        "bzip2" => extension.push_str(".bz2"),
        _ => {}
    }
    root.join(dataset["source"].as_str().expect("validated source"))
        .join(dataset["name"].as_str().expect("validated name"))
        .join(dataset["version"].as_str().expect("validated version"))
        .join(format!(
            "{}.{}",
            artifact["name"].as_str().expect("validated artifact name"),
            extension
        ))
}

fn write_selector(path: &Path, selector: &Selector) -> Result<()> {
    if path.exists() {
        return Err(Error::new(
            "cache",
            format!("selector already exists: {}", path.display()),
        ));
    }
    let mut data = BTreeMap::new();
    data.insert("schema_version", json!(selector.schema_version));
    data.insert("release", json!(selector.release));
    data.insert("index_sha256", json!(selector.index_sha256));
    data.insert("index_url", json!(selector.index_url));
    let mut bytes =
        serde_json::to_vec(&data).map_err(|error| Error::new("cache", error.to_string()))?;
    bytes.push(b'\n');
    let parent = path
        .parent()
        .ok_or_else(|| Error::new("cache", "selector path has no parent"))?;
    fs::create_dir_all(parent).map_err(|error| Error::new("cache", error.to_string()))?;
    let mut temporary =
        NamedTempFile::new_in(parent).map_err(|error| Error::new("cache", error.to_string()))?;
    temporary
        .write_all(&bytes)
        .map_err(|error| Error::new("cache", error.to_string()))?;
    temporary
        .as_file_mut()
        .sync_all()
        .map_err(|error| Error::new("cache", error.to_string()))?;
    temporary
        .persist_noclobber(path)
        .map_err(|error| Error::new("cache", error.error.to_string()))?;
    Ok(())
}

fn print_json(value: &impl serde::Serialize) -> Result<()> {
    let text = serde_json::to_string_pretty(value)
        .map_err(|error| Error::new("cache", error.to_string()))?;
    println!("{text}");
    Ok(())
}
