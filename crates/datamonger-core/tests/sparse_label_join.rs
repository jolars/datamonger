use datamonger_core::{decode_sparse_label_join, ErrorKind, Values};

#[test]
fn joins_by_id_in_shard_order() {
    let inputs = vec![
        &include_bytes!("fixtures/conformance/artifacts/sparse-join-labels.txt")[..],
        &include_bytes!("fixtures/conformance/artifacts/sparse-join-train_one.txt")[..],
        &include_bytes!("fixtures/conformance/artifacts/sparse-join-train_two.txt")[..],
        &include_bytes!("fixtures/conformance/artifacts/sparse-join-test.txt")[..],
    ];
    let components = decode_sparse_label_join(inputs, 2, 4, 2, &mut || Ok(())).unwrap();
    assert_eq!(components[0].values, Values::Float64(vec![0.125, 0.5]));
    assert_eq!(components[2].values, Values::Int64(vec![20, 10]));
    assert_eq!(components[5].values, Values::Int64(vec![30]));
    assert_eq!(
        components[6].values,
        Values::String(vec!["A".into(), "Z".into()])
    );
}

#[test]
fn rejects_duplicate_missing_and_unmatched_ids() {
    let valid_labels = &b"A 1 1\nA 2 1\n"[..];
    let valid_train = &b"1 1:0.5\n"[..];
    let valid_test = &b"2 1:0.75\n"[..];
    for (labels, train, test) in [
        (&b"A 1 1\nA 1 1\nA 2 1\n"[..], valid_train, valid_test),
        (valid_labels, valid_train, valid_train),
        (valid_labels, valid_train, &b"3 1:0.5\n"[..]),
        (valid_labels, valid_train, &b""[..]),
        (valid_labels, &b"01 1:0.5\n"[..], valid_test),
        (valid_labels, &b"1 1:0.5 1:0.25\n"[..], valid_test),
    ] {
        let error = decode_sparse_label_join(vec![labels, train, test], 1, 1, 1, &mut || Ok(()))
            .unwrap_err();
        assert_eq!(error.kind, ErrorKind::Decode);
    }
}
