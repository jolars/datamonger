# Prepare RCV1-v2 Topics

This recipe prepares the topic classification benchmark for
`datamonger:lewis2004@1`. See [DATASET.md](DATASET.md) for dataset
documentation and [RIGHTS.md](RIGHTS.md) for the review of redistribution
rights.

Datamonger can fetch and decode the six Figshare artifacts directly. This
standalone recipe provides a local LIBSVM export for comparison.

Run from the repository root in the devenv shell. The recipe uses Python's
standard library and was run with Python 3.14.7 and zlib 1.3.2. Keep both
the downloads and the prepared files outside the repository.

```sh
work=$(mktemp -d)
for file in 5976048 5976057 5976069 5976066 5976063 5976060; do
  curl -fLsS "https://ndownloader.figshare.com/files/$file" -o "$work/$file" || break
done
python curation/lewis2004/1/prepare.py "$work" "$work/prepared"
```

The six Figshare files are the original appendix data distributed through
[scikit-learn's RCV1 loader](https://github.com/scikit-learn/scikit-learn/blob/1.9.0/sklearn/datasets/_rcv1.py).
The recipe checks the compressed sizes and SHA-256 digests before reading
the files. The [JMLR appendix directory](https://jmlr.csail.mit.edu/papers/volume5/lewis04a/a13-vector-files/)
serves matching test parts 0 and 1. Its training file and test parts 2 and 3
contain tokenized records under the vector filenames. The recipe uses the
complete vector files referenced by scikit-learn.

| Figshare file ID | LYRL2004 input |
| --- | --- |
| 5976048 | Appendix 8 topic assignments |
| 5976057 | Appendix 13 training vectors |
| 5976069 | Appendix 13 test vectors, part 0 |
| 5976066 | Appendix 13 test vectors, part 1 |
| 5976063 | Appendix 13 test vectors, part 2 |
| 5976060 | Appendix 13 test vectors, part 3 |

The [registry manifest](../../../registry/datasets/datamonger/lewis2004-1.yaml)
specifies the shard order, task roles, and decoded verification digest. The
documents and topics CSVs in the standalone export correspond to
`document_id` and `label_codes` on each fetched split.

The test vectors contain 338 document IDs above 810596, the upper bound
printed in §5.1 of the paper. The decoder follows the published shard
membership and retains all 781,265 test rows.
