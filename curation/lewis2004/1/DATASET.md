# RCV1-v2 Topics

RCV1-v2 is a corrected benchmark of Reuters English-language newswire
articles. Each row represents one article and has one or more of 103 topic
codes. The data follow the chronological split defined by Lewis et al.

| Split | Publication dates | Documents |
| --- | --- | ---: |
| Train | August 20–31, 1996 | 23,149 |
| Test | September 1, 1996–August 19, 1997 | 781,265 |

The 47,236 feature columns retain the numeric term IDs from the published
vectors. Feature values are the authors' cosine-normalized, log term frequency
by inverse document frequency weights over stemmed terms. An omitted feature
has value zero. The paper recommends using the vectors with the original split
because the vocabulary and weights were determined before the cutoff.

Datamonger downloads the vectors and topic assignments from their upstream
locations and joins the published topic assignments to the feature vectors
by Reuters document ID. It keeps the feature indices and weights and preserves
the order in each source file. The test file combines the four original test
parts in part-number order.

The fetched training and test splits expose sparse `features` and `response`
matrices alongside `document_id` and `label_codes`. The standalone export
provides the same data in the following files.

- `train.libsvm.gz` and `test.libsvm.gz` contain gzipped multilabel LIBSVM rows.
  The first field lists zero-based topic IDs. The remaining fields contain
  one-based feature indices and their weights.
- `train-documents.csv` and `test-documents.csv` give the Reuters document ID
  for each row of the corresponding vector file.
- `topics.csv` maps response columns to topic codes in lexicographic order.
  The assigned topics have value one in the response and the others have
  value zero.

Cite David D. Lewis, Yiming Yang, Tony G. Rose, and Fan Li (2004).
*RCV1: A New Benchmark Collection for Text Categorization Research*.
Journal of Machine Learning Research 5, 361–397. Acknowledge Reuters as the
source corpus provider. [Benchmark paper](https://jmlr.org/papers/v5/lewis04a.html)

Reuters authorized the authors to distribute their vector files without a
license agreement. The scope of that permission for redistribution of these
reformatted files remains unresolved. [Paper, §7](https://jmlr.org/papers/volume5/lewis04a/lewis04a.pdf)
