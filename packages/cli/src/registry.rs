use std::collections::HashSet;
use std::fs;
use std::path::Path;

use jsonschema::Registry;
use reqwest::Url;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

use crate::error::{Error, Result};

pub const BUNDLED_INDEX: &[u8] = include_bytes!("../assets/index.json");
const BUNDLED_SELECTOR: &[u8] = include_bytes!("../assets/selector.json");
const SCHEMAS: [(&str, &str); 5] = [
    (
        "https://datamonger.dev/spec/schema/index-v1.schema.json",
        include_str!("../assets/index-v1.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/manifest-v1.schema.json",
        include_str!("../assets/manifest-v1.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/erratum-v1.schema.json",
        include_str!("../assets/erratum-v1.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/selector-v1.schema.json",
        include_str!("../assets/selector-v1.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/catalog-v1.schema.json",
        include_str!("../assets/catalog-v1.schema.json"),
    ),
];

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Selector {
    pub schema_version: u64,
    pub release: String,
    pub index_sha256: String,
    pub index_url: String,
}

impl Selector {
    pub fn is_bundled(&self) -> bool {
        let bundled = bundled_selector().expect("bundled selector is valid");
        self.release == bundled.release && self.index_sha256 == bundled.index_sha256
    }
}

pub struct Index {
    pub selector: Selector,
    pub document: Value,
}

pub fn sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

fn validate_schema(value: &Value, schema_name: &str) -> Result<()> {
    let mut registry = Registry::new();
    for (uri, raw) in SCHEMAS {
        let schema: Value = serde_json::from_str(raw)
            .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
        registry = registry
            .add(uri, schema)
            .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    }
    let registry = registry
        .prepare()
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    let schema = serde_json::json!({
        "$ref": format!("https://datamonger.dev/spec/schema/{schema_name}-v1.schema.json")
    });
    let validator = jsonschema::options()
        .with_registry(&registry)
        .offline()
        .build(&schema)
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    if let Err(error) = validator.validate(value) {
        return Err(Error::new(
            "unsupported-registry",
            format!("{schema_name} schema validation failed: {error}"),
        ));
    }
    Ok(())
}

pub fn parse_selector(bytes: &[u8]) -> Result<Selector> {
    let value: Value = serde_json::from_slice(bytes).map_err(|error| {
        Error::new(
            "unsupported-registry",
            format!("invalid selector JSON: {error}"),
        )
    })?;
    validate_schema(&value, "selector")?;
    let selector: Selector = serde_json::from_value(value)
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    let url = Url::parse(&selector.index_url)
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    if !matches!(url.scheme(), "http" | "https") || url.host_str().is_none() {
        return Err(Error::new("unsupported-registry", "invalid index URL"));
    }
    Ok(selector)
}

pub fn bundled_selector() -> Result<Selector> {
    parse_selector(BUNDLED_SELECTOR)
}

pub fn active_selector(explicit: Option<&Path>, cwd: &Path) -> Result<Selector> {
    if let Some(path) = explicit {
        return read_selector(path);
    }
    let start = cwd
        .canonicalize()
        .map_err(|error| Error::new("unsupported-registry", error.to_string()))?;
    for directory in start.ancestors() {
        let path = directory.join(".datamonger").join("selector.json");
        match fs::metadata(&path) {
            Ok(_) => return read_selector(&path),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(Error::new("unsupported-registry", error.to_string())),
        }
    }
    bundled_selector()
}

fn read_selector(path: &Path) -> Result<Selector> {
    let bytes = fs::read(path).map_err(|error| {
        Error::new(
            "unsupported-registry",
            format!("cannot read selector {}: {error}", path.display()),
        )
    })?;
    parse_selector(&bytes)
}

pub fn parse_catalog(bytes: &[u8], release: &str) -> Result<Selector> {
    let value: Value = serde_json::from_slice(bytes).map_err(|error| {
        Error::new(
            "unsupported-registry",
            format!("invalid catalog JSON: {error}"),
        )
    })?;
    validate_schema(&value, "catalog")?;
    let mut seen = HashSet::new();
    let mut result = None;
    for raw in value["releases"].as_array().expect("schema checked array") {
        let selector = parse_selector(
            &serde_json::to_vec(raw)
                .map_err(|error| Error::new("unsupported-registry", error.to_string()))?,
        )?;
        if !seen.insert(selector.release.clone()) {
            return Err(Error::new(
                "unsupported-registry",
                "duplicate catalog release",
            ));
        }
        if selector.release == release {
            result = Some(selector);
        }
    }
    result.ok_or_else(|| Error::new("unsupported-registry", format!("unknown release {release}")))
}

pub fn parse_index(bytes: &[u8], selector: Selector) -> Result<Index> {
    let digest = sha256(bytes);
    if digest != selector.index_sha256 {
        return Err(Error::new(
            "unsupported-registry",
            format!(
                "registry index SHA-256 mismatch: expected {}, got {digest}",
                selector.index_sha256
            ),
        ));
    }
    let value: Value = serde_json::from_slice(bytes).map_err(|error| {
        Error::new(
            "unsupported-registry",
            format!("invalid index JSON: {error}"),
        )
    })?;
    validate_schema(&value, "index")?;
    if value["release"] != selector.release {
        return Err(Error::new(
            "unsupported-registry",
            "registry index release differs from selector",
        ));
    }
    validate_index_semantics(&value)?;
    Ok(Index {
        selector,
        document: value,
    })
}

fn validate_index_semantics(index: &Value) -> Result<()> {
    let mut identities = HashSet::new();
    for dataset in index["datasets"].as_array().expect("schema checked array") {
        let id = dataset_id(dataset);
        if !identities.insert(id) {
            return Err(Error::new(
                "unsupported-registry",
                "duplicate dataset identity",
            ));
        }
        let mut names = HashSet::new();
        for artifact in dataset["artifacts"]
            .as_array()
            .expect("schema checked array")
        {
            let name = artifact["name"].as_str().expect("schema checked string");
            if !names.insert(name) {
                return Err(Error::new(
                    "unsupported-registry",
                    "duplicate artifact name",
                ));
            }
            let mut urls = HashSet::new();
            for download in artifact["downloads"]
                .as_array()
                .expect("schema checked array")
            {
                let url = download["url"].as_str().expect("schema checked string");
                if !urls.insert(url) {
                    return Err(Error::new("unsupported-registry", "duplicate artifact URL"));
                }
            }
        }
        for artifact_name in dataset["representation"]["inputs"]
            .as_object()
            .expect("schema checked object")
            .values()
        {
            if !names.contains(artifact_name.as_str().expect("schema checked string")) {
                return Err(Error::new(
                    "unsupported-registry",
                    "representation refers to unknown artifact",
                ));
            }
        }
    }
    let mut defaults = HashSet::new();
    for default in index["defaults"].as_array().expect("schema checked array") {
        let id = dataset_id(default);
        let key = format!(
            "{}:{}",
            default["source"].as_str().expect("schema checked source"),
            default["name"].as_str().expect("schema checked name")
        );
        if !defaults.insert(key) || !identities.contains(&id) {
            return Err(Error::new(
                "unsupported-registry",
                "duplicate or unresolved default",
            ));
        }
    }
    Ok(())
}

pub fn dataset_id(dataset: &Value) -> String {
    format!(
        "{}:{}@{}",
        dataset["source"].as_str().unwrap_or_default(),
        dataset["name"].as_str().unwrap_or_default(),
        dataset["version"].as_str().unwrap_or_default()
    )
}

pub fn split_id(id: &str) -> Result<(&str, &str, Option<&str>)> {
    let (source, rest) = id
        .split_once(':')
        .ok_or_else(|| Error::new("unknown-dataset", "expected SOURCE:NAME[@VERSION]"))?;
    let (name, version) = match rest.split_once('@') {
        Some((name, version)) => (name, Some(version)),
        None => (rest, None),
    };
    let valid_part = |part: &str| {
        let mut bytes = part.bytes();
        bytes
            .next()
            .is_some_and(|byte| byte.is_ascii_alphanumeric())
            && bytes.all(|byte| {
                byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'+' | b'-')
            })
    };
    if !valid_part(source) || !valid_part(name) || version.is_some_and(|value| !valid_part(value)) {
        return Err(Error::new("unknown-dataset", "invalid dataset identifier"));
    }
    Ok((source, name, version))
}

impl Index {
    pub fn datasets(&self) -> &[Value] {
        self.document["datasets"]
            .as_array()
            .expect("validated index")
    }

    pub fn resolve(&self, id: &str) -> Result<&Value> {
        let (source, name, version) = split_id(id)?;
        let selected_version = match version {
            Some(version) => version,
            None => self.document["defaults"]
                .as_array()
                .expect("validated defaults")
                .iter()
                .find(|entry| entry["source"] == source && entry["name"] == name)
                .and_then(|entry| entry["version"].as_str())
                .ok_or_else(|| Error::new("unknown-dataset", format!("unknown dataset {id}")))?,
        };
        self.datasets()
            .iter()
            .find(|entry| {
                entry["source"] == source
                    && entry["name"] == name
                    && entry["version"] == selected_version
            })
            .ok_or_else(|| Error::new("unknown-dataset", format!("unknown dataset {id}")))
    }
}
