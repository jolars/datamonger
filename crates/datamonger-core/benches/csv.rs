use std::{fmt::Write, hint::black_box};

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use datamonger_core::{
    decode_delimited, parse_binary64, Column, Component, DataType, DelimitedOptions, Shape, Values,
};

fn numeric_csv(rows: usize, columns: &[Column]) -> String {
    let mut input = columns
        .iter()
        .map(|column| column.name.as_str())
        .collect::<Vec<_>>()
        .join(",");
    input.push('\n');
    for row in 0..rows {
        for col in 0..columns.len() {
            if col > 0 {
                input.push(',');
            }
            write!(
                input,
                "{}.{:03}",
                row as i64 - rows as i64 / 2,
                (row + col) % 1000
            )
            .unwrap();
        }
        input.push('\n');
    }
    input
}

fn read_with_csv(input: &[u8], columns: &[Column]) -> Vec<Component> {
    let mut reader = csv::Reader::from_reader(input);
    let header = reader.headers().expect("read CSV header");
    assert!(header.iter().eq(columns.iter().map(|c| c.name.as_str())));

    let mut output: Vec<_> = columns
        .iter()
        .map(|column| Component {
            name: column.name.clone(),
            shape: Shape::Vector,
            values: Values::Float64(Vec::new()),
            valid: Vec::new(),
        })
        .collect();
    let mut record = csv::StringRecord::new();
    while reader.read_record(&mut record).expect("read CSV record") {
        for (component, field) in output.iter_mut().zip(&record) {
            let Values::Float64(values) = &mut component.values else {
                unreachable!("the benchmark only uses float64 columns");
            };
            values.push(parse_binary64(field, false).expect("parse CSV float"));
            component.valid.push(true);
        }
    }
    output
}

fn bench_csv(criterion: &mut Criterion) {
    let mut group = criterion.benchmark_group("csv_numeric");
    for (rows, width) in [(100_000, 4), (10_000, 40)] {
        let options = DelimitedOptions {
            delimiter: b',',
            columns: (0..width)
                .map(|col| Column {
                    name: format!("x{col}"),
                    data_type: DataType::Float64,
                })
                .collect(),
            missing_values: Vec::new(),
        };
        let input = numeric_csv(rows, &options.columns);
        let input = input.as_bytes();
        let datamonger = decode_delimited(input, &options).expect("decode CSV");
        assert!(datamonger.iter().all(|column| column.values.len() == rows));
        assert_eq!(datamonger, read_with_csv(input, &options.columns));
        drop(datamonger);

        let shape = format!("{rows}x{width}");
        group.throughput(Throughput::Bytes(input.len() as u64));
        group.bench_function(BenchmarkId::new("datamonger", &shape), |b| {
            b.iter(|| decode_delimited(black_box(input), &options).expect("decode CSV"));
        });
        group.bench_function(BenchmarkId::new("rust-csv", &shape), |b| {
            b.iter(|| read_with_csv(black_box(input), &options.columns));
        });
    }
    group.finish();
}

criterion_group!(benches, bench_csv);
criterion_main!(benches);
