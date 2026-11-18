use datamonger_core::{
    decode_libsvm_version_with_options, DecodeOptions, LabelType, LibsvmOptions,
};
use std::{env, fs, hint::black_box, time::Instant};

fn main() {
    // Cargo passes --bench to custom harnesses and runs them in test mode too.
    let args: Vec<_> = env::args().skip(1).filter(|arg| arg != "--bench").collect();
    if args.is_empty() {
        return;
    }
    let [path, features, label_type, repeats, version @ ..] = args.as_slice() else {
        panic!("usage: cargo bench -p datamonger-core --bench libsvm -- PATH FEATURES LABEL_TYPE REPEATS [VERSION]");
    };
    let version = match version {
        [] => 1,
        [version] if version == "1" => 1,
        [version] if version == "2" => 2,
        _ => panic!("decoder version must be 1 or 2"),
    };
    let input = fs::read(path).expect("read uncompressed LIBSVM input");
    let options = LibsvmOptions {
        feature_count: features.parse().expect("integer feature count"),
        label_type: match label_type.as_str() {
            "int64" => LabelType::Int64,
            "float64" => LabelType::Float64,
            _ => panic!("label type must be int64 or float64"),
        },
        target_name: "response".into(),
    };
    let repeats: usize = repeats.parse().expect("integer repeat count");
    assert!(repeats > 0, "repeat count must be positive");
    let decode = || {
        decode_libsvm_version_with_options(
            black_box(input.as_slice()),
            &options,
            version,
            DecodeOptions::default(),
        )
        .expect("decode LIBSVM")
    };
    drop(decode());
    let mut samples = Vec::with_capacity(repeats);
    for _ in 0..repeats {
        let start = Instant::now();
        let output = black_box(decode());
        samples.push(start.elapsed().as_secs_f64());
        drop(output);
    }
    samples.sort_by(f64::total_cmp);
    let median = (samples[(repeats - 1) / 2] + samples[repeats / 2]) / 2.0;
    println!(
        "{path}: decoder v{version}, {} bytes, {repeats} samples, median {:.3} ms, {:.1} MiB/s",
        input.len(),
        median * 1e3,
        input.len() as f64 / (1024.0 * 1024.0 * median),
    );
}
