use std::collections::{HashMap, HashSet};
use std::fs::{self, File, OpenOptions, TryLockError};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

use serde::Serialize;
use sha2::{Digest, Sha256};
use tempfile::NamedTempFile;

use crate::error::{Error, Result};
use crate::registry::{BUNDLED_INDEX, dataset_id};

pub fn default_root() -> Result<PathBuf> {
    dirs::cache_dir()
        .map(|path| path.join("datamonger").join("cli"))
        .ok_or_else(|| Error::new("cache", "cannot determine platform cache directory"))
}

fn object_path(root: &Path, namespace: &str, digest: &str) -> PathBuf {
    root.join(namespace).join("sha256").join(digest)
}

fn lock_path(root: &Path, namespace: &str, digest: &str, publication: bool) -> PathBuf {
    let suffix = if publication {
        ".publish.lock"
    } else {
        ".lock"
    };
    root.join(".leases")
        .join(namespace)
        .join("sha256")
        .join(format!("{digest}{suffix}"))
}

struct Lease(File);

impl Lease {
    fn open(path: &Path) -> Result<Self> {
        fs::create_dir_all(path.parent().expect("lock has parent"))
            .map_err(|error| Error::new("cache", error.to_string()))?;
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)
            .map_err(|error| Error::new("cache", error.to_string()))?;
        Ok(Self(file))
    }

    fn shared(path: &Path) -> Result<Self> {
        let lease = Self::open(path)?;
        lease
            .0
            .lock_shared()
            .map_err(|error| Error::new("cache", error.to_string()))?;
        Ok(lease)
    }

    fn exclusive(path: &Path) -> Result<Self> {
        let lease = Self::open(path)?;
        lease
            .0
            .lock()
            .map_err(|error| Error::new("cache", error.to_string()))?;
        Ok(lease)
    }

    fn try_exclusive(path: &Path) -> Result<Option<Self>> {
        let lease = Self::open(path)?;
        match lease.0.try_lock() {
            Ok(()) => Ok(Some(lease)),
            Err(TryLockError::WouldBlock) => Ok(None),
            Err(TryLockError::Error(error)) => Err(Error::new("cache", error.to_string())),
        }
    }
}

impl Drop for Lease {
    fn drop(&mut self) {
        let _ = self.0.unlock();
    }
}

pub struct CachedFile {
    pub path: PathBuf,
    _lease: Lease,
}

fn digest_file(path: &Path) -> Result<(String, u64)> {
    let mut file = File::open(path).map_err(|error| Error::new("cache", error.to_string()))?;
    let mut hasher = Sha256::new();
    let mut total = 0_u64;
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|error| Error::new("cache", error.to_string()))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
        total += count as u64;
    }
    Ok((hex::encode(hasher.finalize()), total))
}

fn matches(path: &Path, digest: &str, size: Option<u64>) -> Result<bool> {
    if !path.exists() {
        return Ok(false);
    }
    let (actual, actual_size) = digest_file(path)?;
    Ok(actual == digest && size.is_none_or(|expected| actual_size == expected))
}

pub fn verify_path(path: &Path, digest: &str, size: u64) -> Result<bool> {
    matches(path, digest, Some(size))
}

pub fn get_or_fetch<F>(
    root: &Path,
    namespace: &str,
    digest: &str,
    size: Option<u64>,
    integrity_category: &'static str,
    offline: bool,
    download: F,
) -> Result<CachedFile>
where
    F: FnOnce(&mut NamedTempFile) -> Result<()>,
{
    let path = object_path(root, namespace, digest);
    let lease = Lease::shared(&lock_path(root, namespace, digest, false))?;
    if matches(&path, digest, size)? {
        return Ok(CachedFile {
            path,
            _lease: lease,
        });
    }
    if offline {
        let category = if namespace == "registries" {
            "unsupported-registry"
        } else {
            "artifact-offline"
        };
        return Err(Error::new(
            category,
            format!("no valid cached {namespace} object"),
        ));
    }
    fs::create_dir_all(path.parent().expect("cache object has parent"))
        .map_err(|error| Error::new("cache", error.to_string()))?;
    let mut temporary = NamedTempFile::new_in(path.parent().expect("cache object has parent"))
        .map_err(|error| Error::new("cache", error.to_string()))?;
    download(&mut temporary)?;
    temporary
        .as_file_mut()
        .sync_all()
        .map_err(|error| Error::new("cache", error.to_string()))?;
    let (actual, actual_size) = digest_file(temporary.path())?;
    if actual != digest || size.is_some_and(|expected| actual_size != expected) {
        return Err(Error::new(
            integrity_category,
            format!(
                "object integrity mismatch: expected {digest} and {size:?} bytes, got {actual} and {actual_size} bytes"
            ),
        ));
    }
    let _publication = Lease::exclusive(&lock_path(root, namespace, digest, true))?;
    if !matches(&path, digest, size)? {
        temporary
            .persist(&path)
            .map_err(|error| Error::new("cache", error.error.to_string()))?;
    }
    Ok(CachedFile {
        path,
        _lease: lease,
    })
}

pub fn read_cached(file: &CachedFile) -> Result<Vec<u8>> {
    fs::read(&file.path).map_err(|error| Error::new("cache", error.to_string()))
}

#[derive(Clone, Serialize)]
pub struct Entry {
    pub kind: String,
    pub sha256: String,
    pub size: u64,
    pub modified_unix_seconds: u64,
    pub path: PathBuf,
    pub valid: bool,
    pub datasets: Vec<String>,
    pub registry_release: Option<String>,
}

#[derive(Serialize)]
pub struct Inventory {
    pub location: PathBuf,
    pub total_size: u64,
    pub entries: Vec<Entry>,
}

fn references(value: &serde_json::Value, target: &mut HashMap<String, HashSet<String>>) {
    if let Some(datasets) = value["datasets"].as_array() {
        for dataset in datasets {
            let id = dataset_id(dataset);
            if let Some(artifacts) = dataset["artifacts"].as_array() {
                for artifact in artifacts {
                    if let Some(digest) = artifact["sha256"].as_str() {
                        target
                            .entry(digest.to_owned())
                            .or_default()
                            .insert(id.clone());
                    }
                }
            }
        }
    }
}

pub fn inventory(root: &Path) -> Result<Inventory> {
    let mut entries = Vec::new();
    let mut refs = HashMap::new();
    let bundled: serde_json::Value = serde_json::from_slice(BUNDLED_INDEX)
        .map_err(|error| Error::new("cache", error.to_string()))?;
    references(&bundled, &mut refs);
    for (namespace, kind) in [("registries", "registry"), ("objects", "artifact")] {
        let directory = root.join(namespace).join("sha256");
        let paths = match fs::read_dir(&directory) {
            Ok(paths) => paths,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(Error::new("cache", error.to_string())),
        };
        for item in paths {
            let path = item
                .map_err(|error| Error::new("cache", error.to_string()))?
                .path();
            let digest = path
                .file_name()
                .and_then(|name| name.to_str())
                .unwrap_or("");
            if digest.len() != 64
                || !digest
                    .bytes()
                    .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
            {
                continue;
            }
            if !path.is_file() || path.is_symlink() {
                continue;
            }
            let _lease = Lease::shared(&lock_path(root, namespace, digest, false))?;
            let (actual, size) = digest_file(&path)?;
            let metadata =
                fs::metadata(&path).map_err(|error| Error::new("cache", error.to_string()))?;
            let modified_unix_seconds = metadata
                .modified()
                .ok()
                .and_then(|value| value.duration_since(UNIX_EPOCH).ok())
                .map_or(0, |value| value.as_secs());
            let valid = actual == digest;
            let registry_release = if kind == "registry" && valid {
                let bytes =
                    fs::read(&path).map_err(|error| Error::new("cache", error.to_string()))?;
                let value: serde_json::Value = serde_json::from_slice(&bytes).unwrap_or_default();
                references(&value, &mut refs);
                value["release"].as_str().map(str::to_owned)
            } else {
                None
            };
            entries.push(Entry {
                kind: kind.to_owned(),
                sha256: digest.to_owned(),
                size,
                modified_unix_seconds,
                path,
                valid,
                datasets: Vec::new(),
                registry_release,
            });
        }
    }
    for entry in &mut entries {
        if entry.kind == "artifact" {
            entry.datasets = refs
                .get(&entry.sha256)
                .map(|value| {
                    let mut result: Vec<_> = value.iter().cloned().collect();
                    result.sort();
                    result
                })
                .unwrap_or_default();
        }
    }
    entries.sort_by(|left, right| (&left.kind, &left.sha256).cmp(&(&right.kind, &right.sha256)));
    Ok(Inventory {
        location: root.to_path_buf(),
        total_size: entries.iter().map(|entry| entry.size).sum(),
        entries,
    })
}

#[derive(Serialize)]
pub struct CleanResult {
    pub location: PathBuf,
    pub removed: Vec<Entry>,
    pub skipped: Vec<Entry>,
    pub bytes_removed: u64,
}

pub fn clean(root: &Path, dataset: Option<&str>, all: bool) -> Result<CleanResult> {
    if !all && dataset.is_none() {
        return Err(Error::new(
            "cache",
            "cache clean requires --dataset or --all",
        ));
    }
    let current = inventory(root)?;
    let mut removed = Vec::new();
    let mut skipped = Vec::new();
    for entry in current.entries {
        if dataset.is_some_and(|id| {
            entry.kind != "artifact" || !entry.datasets.iter().any(|value| value == id)
        }) {
            continue;
        }
        let namespace = if entry.kind == "registry" {
            "registries"
        } else {
            "objects"
        };
        let Some(_lease) = Lease::try_exclusive(&lock_path(root, namespace, &entry.sha256, false))?
        else {
            skipped.push(entry);
            continue;
        };
        // Inventory is a snapshot; a writer may have replaced the object before this lock.
        if entry.path.exists()
            && fs::metadata(&entry.path)
                .map_err(|error| Error::new("cache", error.to_string()))?
                .len()
                == entry.size
            && matches(&entry.path, &entry.sha256, None)? == entry.valid
        {
            fs::remove_file(&entry.path).map_err(|error| Error::new("cache", error.to_string()))?;
            removed.push(entry);
        } else {
            skipped.push(entry);
        }
    }
    let bytes_removed = removed.iter().map(|entry| entry.size).sum();
    Ok(CleanResult {
        location: root.to_path_buf(),
        removed,
        skipped,
        bytes_removed,
    })
}

pub fn copy_verified(source: &CachedFile, target: &Path, digest: &str, size: u64) -> Result<()> {
    fs::create_dir_all(target.parent().expect("export has parent"))
        .map_err(|error| Error::new("cache", error.to_string()))?;
    if target.exists() {
        return Err(Error::new(
            "cache",
            format!("output already exists: {}", target.display()),
        ));
    }
    let mut temporary = NamedTempFile::new_in(target.parent().expect("export has parent"))
        .map_err(|error| Error::new("cache", error.to_string()))?;
    let mut input =
        File::open(&source.path).map_err(|error| Error::new("cache", error.to_string()))?;
    std::io::copy(&mut input, temporary.as_file_mut())
        .map_err(|error| Error::new("cache", error.to_string()))?;
    temporary
        .as_file_mut()
        .sync_all()
        .map_err(|error| Error::new("cache", error.to_string()))?;
    let (actual, actual_size) = digest_file(temporary.path())?;
    if actual != digest || actual_size != size {
        return Err(Error::new(
            "artifact-integrity",
            "exported file failed verification",
        ));
    }
    temporary
        .persist_noclobber(target)
        .map_err(|error| Error::new("cache", error.error.to_string()))?;
    Ok(())
}
