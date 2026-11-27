# RCV1-v2 redistribution review

The source review on 2026-11-27 covered the LYRL2004 topic assignments
and document vectors. The basis for redistributing the converted benchmark
remains unresolved.

- NIST distributes the original Reuters story corpus under organizational and
  individual agreements. The organizational agreement limits use to specified
  research and development and permits publication of certain derived analyses
  when reconstruction is impossible. It reserves distribution rights in the
  corpus. [NIST corpus page](https://trec.nist.gov/data/reuters/reuters.html)
  and [organizational agreement](https://trec.nist.gov/data/reuters/org_appl_reuters_v4.html).
- Lewis et al. identify the topic assignments as Online Appendix 8 and the
  vectors as Online Appendix 13. Section 7 reports Reuters' permission for the
  authors to distribute the token and vector files without a license agreement.
  The paper gives no downstream redistribution terms for the vectors,
  topic assignments, or a derivative that joins them.
  [Benchmark paper](https://jmlr.org/papers/volume5/lewis04a/lewis04a.pdf).
- The Figshare files used by scikit-learn supply the public downloads for the
  local trial. Their availability and the loader's software license do not
  supply a redistribution grant for this dataset.
  [scikit-learn loader](https://github.com/scikit-learn/scikit-learn/blob/1.9.0/sklearn/datasets/_rcv1.py).

A public deposit requires a documented redistribution basis covering the
numeric vectors, topic assignments, and document ID lookups.
