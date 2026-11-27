# URL Reputation

URL Reputation is an anonymized subset of the data used in the authors’
ICML 2009 study of malicious URL detection. UCI reports 2,396,130 examples
and 3,231,961 possible feature indices. The sparse features encode lexical
and host-based properties. Feature identities are anonymized, and
`FeatureTypes` lists the indices of real-valued features. The remaining
features are binary. Omitted features represent zeros. UCI reports no
missing values. [UCI dataset](https://doi.org/10.24432/C5H89Q),
[authors’ project page](https://www.sysnet.ucsd.edu/projects/url/)

Each SVM-light row contains a classification label followed by sparse
features for one URL. The source labels are `+1` for malicious and `-1`
for benign. The source partitions the examples by day into 121 files
numbered from 0 to 120. It supplies no predefined training and test split.

Datamonger extracted the original day files from the UCI archive and
compressed each one separately with gzip. Decompressing a file recovers
the original bytes, including the labels, feature indices, and row order.
The day files are distributed across two records.

## Citation and license

Ma, J., Saul, L. K., Savage, S., and Voelker, G. M. (2009). URL Reputation
[Dataset]. UCI Machine Learning Repository. [Dataset DOI](https://doi.org/10.24432/C5H89Q)

Ma, J., Saul, L. K., Savage, S., and Voelker, G. M. (2009). Identifying
Suspicious URLs: An Application of Large-Scale Online Learning.
*Proceedings of the 26th International Conference on Machine Learning*,
681–688. [Paper](https://icml.cc/Conferences/2009/papers/42.pdf)

UCI distributes this dataset under the Creative Commons Attribution 4.0
International license. [UCI license statement](https://archive.ics.uci.edu/dataset/187/url+reputation),
[License terms](https://creativecommons.org/licenses/by/4.0/)
