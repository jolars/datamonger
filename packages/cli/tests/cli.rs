use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::Path;
use std::process::{Command, Output};
use std::thread;
use std::time::{Duration, Instant};

use flate2::Compression;
use flate2::write::GzEncoder;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use tempfile::TempDir;

const FIXTURE_INDEX: &[u8] =
    include_bytes!("../../../tests/registry/releases/test-0001/index.json");
const ARTIFACT: &[u8] = include_bytes!("../../../tests/conformance/artifacts/mixed.csv");
const SECOND_ARTIFACT: &[u8] = include_bytes!("../../../tests/conformance/artifacts/mixed.tsv");

fn sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

fn command(cwd: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_datamonger"))
        .current_dir(cwd)
        .args(args)
        .output()
        .expect("CLI starts")
}

fn server(
    responses: impl FnOnce(&str) -> Vec<(&'static str, Vec<u8>)>,
) -> (String, thread::JoinHandle<()>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    listener.set_nonblocking(true).unwrap();
    let address = format!("http://{}", listener.local_addr().unwrap());
    let responses = responses(&address);
    let task = thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(15);
        for (headers, body) in responses {
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        assert!(
                            Instant::now() < deadline,
                            "timed out waiting for HTTP request"
                        );
                        thread::sleep(Duration::from_millis(5));
                    }
                    Err(error) => panic!("HTTP accept failed: {error}"),
                }
            };
            stream.set_nonblocking(false).unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(5)))
                .unwrap();
            let mut request = [0_u8; 1024];
            let _ = stream.read(&mut request).unwrap();
            write!(
                stream,
                "HTTP/1.1 200 OK\r\nContent-Length: {}\r\n{headers}\r\n",
                body.len()
            )
            .unwrap();
            stream.write_all(&body).unwrap();
        }
    });
    (address, task)
}

fn fixture_selector(dir: &TempDir, index: &[u8], url: &str) -> String {
    let selector = json!({
        "schema_version": 1,
        "release": "test-0001",
        "index_sha256": sha256(index),
        "index_url": format!("{url}/index.json")
    });
    let path = dir.path().join("selector.json");
    fs::write(&path, serde_json::to_vec(&selector).unwrap()).unwrap();
    path.to_str().unwrap().to_owned()
}

fn fixture_index(base: &str) -> Vec<u8> {
    let mut index: Value = serde_json::from_slice(FIXTURE_INDEX).unwrap();
    index["datasets"].as_array_mut().unwrap().truncate(1);
    index["defaults"].as_array_mut().unwrap().truncate(1);
    index["datasets"][0]["artifacts"][0]["downloads"] = json!([
        {"kind": "upstream", "url": format!("{base}/bad")},
        {"kind": "upstream", "url": format!("{base}/good")}
    ]);
    serde_json::to_vec(&index).unwrap()
}

fn two_artifact_index(base: &str) -> Vec<u8> {
    let mut index: Value = serde_json::from_slice(FIXTURE_INDEX).unwrap();
    index["datasets"].as_array_mut().unwrap().truncate(1);
    index["defaults"].as_array_mut().unwrap().truncate(1);
    let first = &mut index["datasets"][0]["artifacts"][0];
    first["downloads"] = json!([{"kind": "upstream", "url": format!("{base}/first")}]);
    let mut second = first.clone();
    second["name"] = json!("second");
    second["format"] = json!("tsv");
    second["sha256"] = json!(sha256(SECOND_ARTIFACT));
    second["size"] = json!(SECOND_ARTIFACT.len());
    second["downloads"] = json!([{"kind": "upstream", "url": format!("{base}/second")}]);
    index["datasets"][0]["artifacts"]
        .as_array_mut()
        .unwrap()
        .push(second);
    serde_json::to_vec(&index).unwrap()
}

#[test]
fn bundled_registry_works_offline() {
    let dir = TempDir::new().unwrap();
    let output = command(
        dir.path(),
        &["--offline", "--json", "list", "--source", "uci"],
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["registry"]["release"], "2026.09");
    assert!(
        value["datasets"]
            .as_array()
            .unwrap()
            .iter()
            .all(|entry| entry["dataset_id"].as_str().unwrap().starts_with("uci:"))
    );

    let info = command(dir.path(), &["--offline", "info", "uci:iris"]);
    assert!(info.status.success());
    let detail = String::from_utf8(info.stdout).unwrap();
    assert!(detail.contains("Distribution: upstream-only"));
    assert!(detail.contains("Verification on fetch: artifact bytes only"));

    let bad = command(
        dir.path(),
        &["--offline", "--json", "info", "uci:iris@bad/version"],
    );
    assert!(!bad.status.success());
    let error: Value = serde_json::from_slice(&bad.stderr).unwrap();
    assert_eq!(error["error"]["category"], "unknown-dataset");
}

#[test]
fn fetch_tries_next_location_verifies_and_exports_raw_bytes() {
    let dir = TempDir::new().unwrap();
    let (base, task) = server(|base| {
        vec![
            ("", fixture_index(base)),
            ("", b"corrupt".to_vec()),
            ("Content-Encoding: gzip\r\n", {
                let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
                encoder.write_all(ARTIFACT).unwrap();
                encoder.finish().unwrap()
            }),
        ]
    });
    let bytes = fixture_index(&base);
    let selector = fixture_selector(&dir, &bytes, &base);
    let cache = dir.path().join("cache");
    let export = dir.path().join("export");
    let output = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--json",
            "fetch",
            "conformance:mixed_csv",
            "--output-dir",
            export.to_str().unwrap(),
        ],
    );
    task.join().unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["verification"], "artifact");
    let output_path = report["artifacts"][0]["output_path"].as_str().unwrap();
    assert_eq!(fs::read(output_path).unwrap(), ARTIFACT);

    let again = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--offline",
            "--json",
            "fetch",
            "conformance:mixed_csv@1",
        ],
    );
    assert!(
        again.status.success(),
        "{}",
        String::from_utf8_lossy(&again.stderr)
    );
    let collision = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--offline",
            "--json",
            "fetch",
            "conformance:mixed_csv@1",
            "--output-dir",
            export.to_str().unwrap(),
        ],
    );
    assert!(!collision.status.success());
    assert_eq!(fs::read(output_path).unwrap(), ARTIFACT);

    let cache_path = report["artifacts"][0]["cache_path"].as_str().unwrap();
    fs::write(cache_path, b"corrupt").unwrap();
    let invalid = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--offline",
            "--json",
            "fetch",
            "conformance:mixed_csv@1",
        ],
    );
    assert!(!invalid.status.success());
    let error: Value = serde_json::from_slice(&invalid.stderr).unwrap();
    assert_eq!(error["error"]["category"], "artifact-offline");
    let inventory = command(
        dir.path(),
        &[
            "--cache-dir",
            cache.to_str().unwrap(),
            "--json",
            "cache",
            "list",
        ],
    );
    let listed: Value = serde_json::from_slice(&inventory.stdout).unwrap();
    assert!(
        listed["entries"]
            .as_array()
            .unwrap()
            .iter()
            .any(|entry| entry["kind"] == "artifact" && entry["valid"] == false)
    );
    let cleaned = command(
        dir.path(),
        &[
            "--cache-dir",
            cache.to_str().unwrap(),
            "--json",
            "cache",
            "clean",
            "--all",
        ],
    );
    assert!(
        cleaned.status.success(),
        "{}",
        String::from_utf8_lossy(&cleaned.stderr)
    );
    assert!(!Path::new(cache_path).exists());
}

#[test]
fn fetch_gets_all_artifacts_unless_one_is_selected() {
    let dir = TempDir::new().unwrap();
    let (base, task) = server(|base| {
        vec![
            ("", two_artifact_index(base)),
            ("", ARTIFACT.to_vec()),
            ("", SECOND_ARTIFACT.to_vec()),
        ]
    });
    let bytes = two_artifact_index(&base);
    let selector = fixture_selector(&dir, &bytes, &base);
    let cache = dir.path().join("cache");
    let fetched = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--json",
            "fetch",
            "conformance:mixed_csv@1",
        ],
    );
    task.join().unwrap();
    assert!(
        fetched.status.success(),
        "{}",
        String::from_utf8_lossy(&fetched.stderr)
    );
    let report: Value = serde_json::from_slice(&fetched.stdout).unwrap();
    assert_eq!(report["artifacts"].as_array().unwrap().len(), 2);
    let selected = command(
        dir.path(),
        &[
            "--selector",
            &selector,
            "--cache-dir",
            cache.to_str().unwrap(),
            "--offline",
            "--json",
            "fetch",
            "conformance:mixed_csv@1",
            "--artifact",
            "second",
        ],
    );
    assert!(
        selected.status.success(),
        "{}",
        String::from_utf8_lossy(&selected.stderr)
    );
    let report: Value = serde_json::from_slice(&selected.stdout).unwrap();
    assert_eq!(report["artifacts"].as_array().unwrap().len(), 1);
    assert_eq!(report["artifacts"][0]["name"], "second");
}
