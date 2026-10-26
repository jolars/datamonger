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
const SCHEMAS: [(&str, &str); 13] = [
    (
        "https://datamonger.dev/spec/schema/index-v5.schema.json",
        include_str!("../assets/index-v5.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/manifest-v5.schema.json",
        include_str!("../assets/manifest-v5.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/index-v4.schema.json",
        include_str!("../assets/index-v4.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/manifest-v4.schema.json",
        include_str!("../assets/manifest-v4.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/index-v3.schema.json",
        include_str!("../assets/index-v3.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/manifest-v3.schema.json",
        include_str!("../assets/manifest-v3.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/index-v2.schema.json",
        include_str!("../assets/index-v2.schema.json"),
    ),
    (
        "https://datamonger.dev/spec/schema/manifest-v2.schema.json",
        include_str!("../assets/manifest-v2.schema.json"),
    ),
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
    let version = value["schema_version"].as_u64().unwrap_or(0);
    let schema = serde_json::json!({
        "$ref": format!("https://datamonger.dev/spec/schema/{schema_name}-v{version}.schema.json")
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

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn libsvm_v2_requires_schema_5() {
        let mut index: Value = serde_json::from_slice(BUNDLED_INDEX).unwrap();
        index["schema_version"] = json!(5);
        let position = index["datasets"]
            .as_array()
            .unwrap()
            .iter()
            .position(|dataset| dataset["representation"]["decoder"] == "libsvm")
            .unwrap();
        index["datasets"][position]["schema_version"] = json!(5);
        index["datasets"][position]["representation"]["decoder_version"] = json!(2);
        validate_schema(&index, "index").unwrap();
        index["datasets"][position]["schema_version"] = json!(4);
        assert!(validate_schema(&index, "index").is_err());
        index["datasets"][position]["schema_version"] = json!(5);
        index["datasets"][position]["representation"]["decoder_version"] = json!(3);
        assert!(validate_schema(&index, "index").is_err());
    }

    fn citation_index() -> Value {
        let mut index: Value = serde_json::from_str(include_str!(
            "../../../tests/registry/releases/test-0001/index.json"
        ))
        .unwrap();
        index["release"] = json!(bundled_selector().unwrap().release);
        index["schema_version"] = json!(2);
        index["datasets"][0]["schema_version"] = json!(2);
        let provenance = index["datasets"][0]["provenance"].as_object_mut().unwrap();
        provenance.remove("citation");
        provenance.insert(
            "citations".into(),
            json!([
                {"citation": "Deposit.", "role": "dataset", "recommended": true},
                {"citation": "Paper.", "role": "paper", "recommended": true},
                {"citation": "Collection.", "role": "collection", "note": "Distribution source."}
            ]),
        );
        index
    }

    #[test]
    fn citation_indexes_accept_mixed_manifest_versions() {
        let index = citation_index();
        let bytes = serde_json::to_vec(&index).unwrap();
        let mut selector = bundled_selector().unwrap();
        selector.index_sha256 = sha256(&bytes);
        let parsed = parse_index(&bytes, selector).unwrap();
        assert_eq!(
            parsed.document["datasets"][0]["provenance"]["citations"]
                .as_array()
                .unwrap()
                .len(),
            3
        );
    }

    #[test]
    fn citation_schemas_reject_ambiguous_or_invalid_records() {
        let mut index = citation_index();
        index["schema_version"] = json!(1);
        assert!(validate_schema(&index, "index").is_err());
        index["schema_version"] = json!(2);
        index["datasets"][0]["provenance"]["citations"][0]["recommended"] = json!(1);
        assert!(validate_schema(&index, "index").is_err());
        index["datasets"][0]["provenance"]["citations"][0]["recommended"] = json!(true);
        index["datasets"][0]["provenance"]["citation"] = json!("Ambiguous legacy citation.");
        assert!(validate_schema(&index, "index").is_err());
    }

    #[test]
    fn named_splits_preserve_feature_only_test_data() {
        let mut index = citation_index();
        index["schema_version"] = json!(4);
        let dataset = &mut index["datasets"][0];
        dataset["schema_version"] = json!(4);
        let original = dataset["representation"].clone();
        let artifact = original["inputs"]["data"].clone();
        dataset["representation"] = json!({
            "decoder": "named-splits", "decoder_version": 1,
            "inputs": {"train": artifact, "test": artifact},
            "options": {"splits": [
                {"name": "train", "decoder": original["decoder"],
                 "decoder_version": 1, "options": original["options"]},
                {"name": "test", "decoder": original["decoder"],
                 "decoder_version": 1, "options": original["options"]},
            ]},
            "expect": original["expect"],
        });
        let component = original["expect"]["components"][0]["name"]
            .as_str()
            .unwrap();
        dataset["tasks"] = json!([{
            "name": "default", "type": "regression", "splits": {
                "train": {"target": format!("train/{component}")},
                "test": {"features": format!("test/{component}")},
            },
        }]);
        let bytes = serde_json::to_vec(&index).unwrap();
        let mut selector = bundled_selector().unwrap();
        selector.index_sha256 = sha256(&bytes);
        let parsed = parse_index(&bytes, selector).unwrap();
        assert_eq!(parsed.document, index);
        index["schema_version"] = json!(3);
        assert!(validate_schema(&index, "index").is_err());
    }

    #[test]
    fn preprocessing_metadata_is_preserved_and_requires_version_3() {
        let mut index = citation_index();
        index["schema_version"] = json!(3);
        index["datasets"][0]["schema_version"] = json!(3);
        let metadata = json!({
            "upstream": {"status": "unknown"},
            "datamonger": {
                "status": "documented",
                "evidence": ["Fixture preparation."],
                "steps": [{
                    "kind": "response-dichotomization",
                    "description": "Prepare a binary response.",
                    "parameters": {"threshold": "7"}
                }]
            }
        });
        index["datasets"][0]["preprocessing"] = metadata.clone();
        let bytes = serde_json::to_vec(&index).unwrap();
        let mut selector = bundled_selector().unwrap();
        selector.index_sha256 = sha256(&bytes);
        let parsed = parse_index(&bytes, selector).unwrap();
        assert_eq!(parsed.document["datasets"][0]["preprocessing"], metadata);
        index["schema_version"] = json!(2);
        assert!(validate_schema(&index, "index").is_err());
        index["schema_version"] = json!(3);
        index["datasets"][0]["preprocessing"]["datamonger"]["steps"][0]["parameters"]["threshold"] =
            json!(7);
        assert!(validate_schema(&index, "index").is_err());
    }
}
