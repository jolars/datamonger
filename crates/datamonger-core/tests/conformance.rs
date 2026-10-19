use std::fs::File;
use std::io::{BufReader, Cursor, Read, Write};
use std::path::{Path, PathBuf};

use datamonger_core::*;
use serde_json::Value;

fn fixtures() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/conformance")
}
fn document(path: &str) -> Value {
    serde_json::from_reader(File::open(fixtures().join(path)).unwrap()).unwrap()
}
fn data_type(value: &str) -> DataType {
    match value {
        "float64" => DataType::Float64,
        "int64" => DataType::Int64,
        "string" => DataType::String,
        "bool" => DataType::Bool,
        _ => panic!("unknown fixture type"),
    }
}
fn svm_options(recipe: &Value) -> LibsvmOptions {
    LibsvmOptions {
        feature_count: recipe["feature_count"].as_u64().unwrap(),
        label_type: if recipe["label_type"] == "int64" {
            LabelType::Int64
        } else {
            LabelType::Float64
        },
        target_name: recipe["target_name"].as_str().unwrap().into(),
    }
}
fn csv_options(recipe: &Value) -> DelimitedOptions {
    DelimitedOptions {
        delimiter: recipe["delimiter"].as_str().unwrap().as_bytes()[0],
        columns: recipe["columns"]
            .as_array()
            .unwrap()
            .iter()
            .map(|c| Column {
                name: c["name"].as_str().unwrap().into(),
                data_type: data_type(c["type"].as_str().unwrap()),
            })
            .collect(),
        missing_values: recipe["missing_values"]
            .as_array()
            .map(|a| a.iter().map(|s| s.as_str().unwrap().into()).collect())
            .unwrap_or_default(),
    }
}
fn decode(case: &Value) -> Result<Vec<Component>> {
    let read =
        |v: &Value| BufReader::new(File::open(fixtures().join(v.as_str().unwrap())).unwrap());
    match case["decoder"].as_str().unwrap() {
        "delimited-text" => decode_delimited(read(&case["input"]), &csv_options(&case["recipe"])),
        "libsvm" => decode_libsvm(read(&case["input"]), &svm_options(&case["recipe"])),
        "libsvm-split" => decode_libsvm_split_with_control(
            read(&case["input"]["train"]),
            read(&case["input"]["test"]),
            &svm_options(&case["recipe"]),
            &mut || Ok(()),
        ),
        _ => panic!("unknown fixture decoder"),
    }
}
fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    bytes
        .iter()
        .flat_map(|b| {
            [
                DIGITS[(b >> 4) as usize] as char,
                DIGITS[(b & 15) as usize] as char,
            ]
        })
        .collect()
}
fn unhex(text: &str) -> Vec<u8> {
    text.as_bytes()
        .chunks_exact(2)
        .map(|b| u8::from_str_radix(std::str::from_utf8(b).unwrap(), 16).unwrap())
        .collect()
}

#[test]
fn shared_decoder_digests() {
    for case in document("cases.json")["cases"].as_array().unwrap() {
        let components = decode(case).unwrap();
        assert_eq!(
            hex(&canonical_sha256(&components).unwrap()),
            case["expected_sha256"].as_str().unwrap(),
            "{}",
            case["id"]
        );
    }
}

fn descriptor(d: &Value) -> Component {
    let values = d["values"].as_array().unwrap();
    let values = match data_type(d["type"].as_str().unwrap()) {
        DataType::Float64 => Values::Float64(
            values
                .iter()
                .map(|v| match v.as_str() {
                    Some("nan") => f64::NAN,
                    Some("-zero") => -0.0,
                    Some("invalid") => 0.0,
                    _ => v.as_f64().unwrap(),
                })
                .collect(),
        ),
        DataType::Int64 => Values::Int64(
            values
                .iter()
                .map(|v| {
                    if v == "invalid" {
                        0
                    } else if let Some(s) = v.as_str() {
                        s.parse().unwrap()
                    } else {
                        v.as_i64().unwrap()
                    }
                })
                .collect(),
        ),
        DataType::String => {
            Values::String(values.iter().map(|v| v.as_str().unwrap().into()).collect())
        }
        DataType::Bool => Values::Bool(values.iter().map(|v| v.as_bool().unwrap()).collect()),
    };
    let shape = match d["kind"].as_str().unwrap() {
        "vector" => Shape::Vector,
        "dense_matrix" => Shape::Dense {
            rows: d["rows"].as_u64().unwrap(),
            columns: d["columns"].as_u64().unwrap(),
        },
        "sparse_matrix" => Shape::Sparse {
            rows: d["rows"].as_u64().unwrap(),
            columns: d["columns"].as_u64().unwrap(),
            row_offsets: d["row_offsets"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_u64().unwrap())
                .collect(),
            column_indices: d["column_indices"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_u64().unwrap())
                .collect(),
        },
        _ => panic!("unknown shape"),
    };
    Component {
        name: d["name"].as_str().unwrap().into(),
        shape,
        values,
        valid: d["valid"]
            .as_array()
            .map(|a| a.iter().map(|v| v.as_bool().unwrap()).collect())
            .unwrap_or_default(),
    }
}

#[test]
fn shared_canonical_bytes() {
    for case in document("canonical/cases.json")["cases"]
        .as_array()
        .unwrap()
    {
        let mut bytes = Vec::new();
        write_canonical(&[descriptor(&case["component"])], &mut bytes).unwrap();
        assert_eq!(
            hex(&bytes),
            case["expected_hex"].as_str().unwrap(),
            "{}",
            case["id"]
        );
    }
}

#[test]
fn shared_malformed_and_fuzz_cases() {
    for case in document("malformed.json")["cases"].as_array().unwrap() {
        assert_eq!(
            decode(case).unwrap_err().kind,
            ErrorKind::Decode,
            "{}",
            case["id"]
        );
    }
    for case in document("fuzz-regressions.json")["cases"]
        .as_array()
        .unwrap()
    {
        let bytes = unhex(case["input_hex"].as_str().unwrap());
        let result = if case["decoder"] == "delimited-text" {
            decode_delimited(
                Cursor::new(bytes),
                &DelimitedOptions {
                    delimiter: b',',
                    columns: vec![Column {
                        name: "x".into(),
                        data_type: DataType::String,
                    }],
                    missing_values: vec![],
                },
            )
        } else {
            decode_libsvm(
                Cursor::new(bytes),
                &svm_options(&document("cases.json")["cases"][2]["recipe"]),
            )
        };
        assert_eq!(
            result.unwrap_err().kind,
            ErrorKind::Decode,
            "{}",
            case["id"]
        );
    }
}

struct OneByte<R>(R);
impl<R: Read> Read for OneByte<R> {
    fn read(&mut self, output: &mut [u8]) -> std::io::Result<usize> {
        if output.is_empty() {
            Ok(0)
        } else {
            self.0.read(&mut output[..1])
        }
    }
}

#[test]
fn short_reads_and_compressed_inputs_agree() {
    let case = &document("cases.json")["cases"][0];
    let input = std::fs::read(fixtures().join(case["input"].as_str().unwrap())).unwrap();
    let options = csv_options(&case["recipe"]);
    let short = decode_delimited(
        BufReader::with_capacity(1, OneByte(Cursor::new(input.clone()))),
        &options,
    )
    .unwrap();
    let digest = canonical_sha256(&short).unwrap();
    let mut gzip = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
    gzip.write_all(&input).unwrap();
    let gzip = gzip.finish().unwrap();
    let mut bzip = bzip2::write::BzEncoder::new(Vec::new(), bzip2::Compression::default());
    bzip.write_all(&input).unwrap();
    let bzip = bzip.finish().unwrap();
    for (bytes, compression) in [(gzip, Compression::Gzip), (bzip, Compression::Bzip2)] {
        let decoded = decode_delimited(
            artifact_reader(Cursor::new(bytes.clone()), compression),
            &options,
        )
        .unwrap();
        assert_eq!(canonical_sha256(&decoded).unwrap(), digest);
        assert!(decode_delimited(
            artifact_reader(Cursor::new(bytes[..bytes.len() - 1].to_vec()), compression),
            &options
        )
        .is_err());
    }
}

#[test]
fn http_gzip_requires_one_complete_member() {
    let mut encoder = flate2::write::GzEncoder::new(Vec::new(), flate2::Compression::default());
    encoder.write_all(b"verified bytes").unwrap();
    let bytes = encoder.finish().unwrap();
    let mut output = Vec::new();
    decode_gzip_single_member(Cursor::new(&bytes), &mut output).unwrap();
    assert_eq!(output, b"verified bytes");
    for prefix in 0..bytes.len() {
        assert!(decode_gzip_single_member(Cursor::new(&bytes[..prefix]), std::io::sink()).is_err());
    }
    let mut invalid = [bytes.clone(), bytes.clone()].concat();
    assert!(decode_gzip_single_member(Cursor::new(&invalid), std::io::sink()).is_err());
    invalid = bytes.clone();
    invalid.push(0);
    assert!(decode_gzip_single_member(Cursor::new(&invalid), std::io::sink()).is_err());
    invalid = bytes.clone();
    invalid[bytes.len() - 8] ^= 1;
    assert!(decode_gzip_single_member(Cursor::new(&invalid), std::io::sink()).is_err());
}

#[test]
fn exact_numeric_conversion_and_invalid_lexemes() {
    assert_eq!(
        parse_binary64(
            "1.00000000000000011102230246251565404236316680908203125",
            false
        )
        .unwrap(),
        1.0
    );
    assert_eq!(
        parse_binary64(
            "1.00000000000000033306690738754696212708950042724609375",
            false
        )
        .unwrap()
        .to_bits(),
        1.0_f64.to_bits() + 2
    );
    assert_eq!(
        parse_binary64("-0.179743", false).unwrap().to_bits(),
        (-0.179743_f64).to_bits()
    );
    assert_eq!(
        parse_binary64("-0", false).unwrap().to_bits(),
        (-0.0_f64).to_bits()
    );
    for value in ["+1", "01", ".5", "1.", "1e", "1e999", "NaN", " 1"] {
        assert!(parse_binary64(value, false).is_err(), "{value}");
    }
    let options = DelimitedOptions {
        delimiter: b',',
        columns: vec![Column {
            name: "x".into(),
            data_type: DataType::Int64,
        }],
        missing_values: vec!["NA".into()],
    };
    let decoded = decode_delimited(
        &b"x\r\n9223372036854775807\r\n-9223372036854775808\r\nNA"[..],
        &options,
    )
    .unwrap();
    assert_eq!(
        decoded[0].values,
        Values::Int64(vec![i64::MAX, i64::MIN, 0])
    );
    assert_eq!(decoded[0].valid, vec![true, true, false]);
}

#[test]
fn writer_errors_and_short_writes_are_preserved() {
    struct Failing;
    impl Write for Failing {
        fn write(&mut self, _: &[u8]) -> std::io::Result<usize> {
            Err(std::io::Error::other("sink failed"))
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let error = write_canonical(&[], Failing).unwrap_err();
    assert_eq!(error.kind, ErrorKind::Io);
    assert!(std::error::Error::source(&error).is_some());

    struct Short(Vec<u8>);
    impl Write for Short {
        fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
            let count = bytes.len().min(3);
            self.0.extend_from_slice(&bytes[..count]);
            Ok(count)
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }
    let mut short = Short(Vec::new());
    write_canonical(&[], &mut short).unwrap();
    assert_eq!(short.0, b"DMCF\x01\x00\x00\x00\x00\x00");
}

#[derive(Default)]
struct BoundedWriter {
    largest: usize,
    bytes: usize,
}
impl Write for BoundedWriter {
    fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
        self.largest = self.largest.max(bytes.len());
        self.bytes += bytes.len();
        Ok(bytes.len())
    }
    fn flush(&mut self) -> std::io::Result<()> {
        Ok(())
    }
}

#[test]
fn emission_is_bounded_and_cancellation_propagates() {
    let component = Component {
        name: "x".into(),
        shape: Shape::Vector,
        values: Values::String(vec!["x".repeat(EMIT_BYTES * 3)]),
        valid: vec![true],
    };
    let mut writer = BoundedWriter::default();
    write_canonical(std::slice::from_ref(&component), &mut writer).unwrap();
    assert!(writer.bytes > EMIT_BYTES * 3);
    assert!(writer.largest <= EMIT_BYTES);
    let mut calls = 0;
    let mut cancel = || {
        calls += 1;
        if calls >= 3 {
            Err(Error::new(ErrorKind::Interrupted, "canceled"))
        } else {
            Ok(())
        }
    };
    assert_eq!(
        write_canonical_with_control(&[component], std::io::sink(), &mut cancel)
            .unwrap_err()
            .kind,
        ErrorKind::Interrupted
    );
    let options = svm_options(&document("cases.json")["cases"][2]["recipe"]);
    let input = b"+1 1:1\n".repeat(2048);
    let mut calls = 0;
    let mut cancel = || {
        calls += 1;
        if calls > 1 {
            Err(Error::new(ErrorKind::Interrupted, "canceled"))
        } else {
            Ok(())
        }
    };
    assert_eq!(
        decode_libsvm_with_control(Cursor::new(input), &options, &mut cancel)
            .unwrap_err()
            .kind,
        ErrorKind::Interrupted
    );
}

#[test]
fn canonical_validation_rejects_invalid_shapes_and_sparse_values() {
    let mut component = Component {
        name: "x".into(),
        shape: Shape::Sparse {
            rows: 1,
            columns: 2,
            row_offsets: vec![0, 2],
            column_indices: vec![1, 0],
        },
        values: Values::Float64(vec![1.0, 2.0]),
        valid: vec![],
    };
    assert_eq!(
        canonical_sha256(&[component.clone()]).unwrap_err().kind,
        ErrorKind::DecodedIntegrity
    );
    component.shape = Shape::Sparse {
        rows: 1,
        columns: 2,
        row_offsets: vec![0, 1],
        column_indices: vec![0],
    };
    for value in [0.0, -0.0, f64::INFINITY] {
        component.values = Values::Float64(vec![value]);
        assert!(canonical_sha256(&[component.clone()]).is_err());
    }
    component.values = Values::Float64(vec![f64::NAN]);
    assert!(canonical_sha256(&[component]).is_ok());
    let dense = Component {
        name: "x".into(),
        shape: Shape::Dense {
            rows: u64::MAX,
            columns: 2,
        },
        values: Values::Int64(vec![]),
        valid: vec![],
    };
    assert!(canonical_sha256(&[dense]).is_err());
}

#[test]
fn julia_float_underflow_compatibility_is_explicit() {
    use datamonger_core::{decode_delimited_with_options, DecodeOptions};
    let options = datamonger_core::DelimitedOptions {
        delimiter: b',',
        columns: vec![datamonger_core::Column {
            name: "x".into(),
            data_type: datamonger_core::DataType::Float64,
        }],
        missing_values: vec![],
    };
    let julia = DecodeOptions {
        reject_float_underflow: true,
    };
    for text in ["x\n1e-999\n", "x\n-1e-999\n"] {
        assert!(datamonger_core::decode_delimited(text.as_bytes(), &options).is_ok());
        assert_eq!(
            decode_delimited_with_options(text.as_bytes(), &options, julia)
                .unwrap_err()
                .kind,
            datamonger_core::ErrorKind::Decode
        );
    }
    for text in ["x\n-0e-999\n", "x\n5e-324\n", "x\n0.0e999\n"] {
        assert_eq!(
            decode_delimited_with_options(text.as_bytes(), &options, julia).unwrap(),
            datamonger_core::decode_delimited(text.as_bytes(), &options).unwrap()
        );
    }
}
