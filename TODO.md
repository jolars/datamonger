# Datamonger TODO

## Decoders

- [x] Support comma-separated multilabel targets in LIBSVM files.
- [ ] Support the LIBSVM string format used by MNIST.
- [x] Support SVMLight ranking files with `qid` fields.
- [ ] Support Excel workbooks (`.xlsx`) such as UCI's Online Retail dataset.

## Graphs and hypergraphs

- [x] Wire graph and HIF decoding into `fetch_data()` in Python, R, and Julia.
- [x] Add manifest and index schema 8 support to the clients, CLI, and registry tooling.
- [x] Register the California, Delaware, and Texas road networks as graph `@2` datasets.
- [x] Register XGI House committees as a hypergraph using the original HIF artifact.
- [ ] Verify canonical digests and public fetches across Python, R, and Julia.
  Check CLI metadata and artifact retrieval.
- [ ] Release the compatible clients, including Julia's rebuilt native library,
  then publish the registry with the new graph and hypergraph entries.
- [ ] Check registry 1.7.0 publication for the existing road edge tables.
  Its configured index download URL returned HTTP 404.

## Datasets

### LIBSVM

Register these catalog entries under the `libsvm` source. See the
[registry collection](registry/collection.yaml) and the
[LIBSVM Data catalog](https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/).

#### Binary classification

- [ ] `australian`
- [ ] `avazu`
- [ ] `breast-cancer`
- [ ] `cod-rna`
- [ ] `criteo`
- [ ] `criteo_tb`
- [ ] `diabetes`
- [x] `duke breast-cancer`
- [ ] `epsilon`
- [ ] `fourclass`
- [ ] `german.numer`
- [ ] `gisette`
- [ ] `HIGGS`
- [ ] `Hyperpartisan News Detection`
- [ ] `ijcnn1`
- [ ] `imdb-sentiment`
- [ ] `ionosphere`
- [ ] `kdd2010 (algebra)`
- [ ] `kdd2010 (bridge to algebra)`
- [ ] `kdd2010 raw version (bridge to algebra)`
- [ ] `kdd2012`
- [x] `leukemia`
- [ ] `liver-disorders`
- [ ] `phishing`
- [ ] `skin_nonskin`
- [ ] `splice`
- [ ] `splice-site`
- [ ] `sonar`
- [ ] `SUSY`
- [ ] `svmguide1`
- [ ] `svmguide3`
- [ ] `url`
- [ ] `webspam`

#### Multiclass classification

- [ ] `aloi`
- [ ] `cifar10`
- [ ] `connect-4`
- [ ] `imdb-rating`
- [ ] `iris`
- [ ] `LEDGAR (LexGLUE)`
- [ ] `letter`
- [ ] `mnist`
- [ ] `mnist8m`
- [x] `news20`
- [ ] `news20 (18,846)`
- [ ] `pendigits`
- [ ] `poker`
- [ ] `protein`
- [ ] `rcv1.multiclass`
- [ ] `SCOTUS (LexGLUE)`
- [ ] `satimage`
- [ ] `sector`
- [ ] `segment`
- [ ] `Sensorless`
- [ ] `shuttle`
- [ ] `smallNORB`
- [ ] `SVHN`
- [ ] `svmguide2`
- [ ] `svmguide4`
- [ ] `usps`
- [ ] `SensIT Vehicle (acoustic)`
- [ ] `SensIT Vehicle (seismic)`
- [ ] `SensIT Vehicle (combined)`
- [ ] `vehicle`
- [ ] `vowel`
- [ ] `wine`

#### Regression

- [ ] `abalone`
- [ ] `bodyfat`
- [ ] `cpusmall`
- [ ] `eunite2001`
- [ ] `housing`
- [ ] `mg`
- [ ] `mpg`
- [ ] `pyrim`
- [ ] `space_ga`

#### Multi-label classification

- [ ] `Amazon-3M`
- [ ] `Wiki-500K`
- [ ] `Amazon-670K`
- [ ] `AmazonCat-13K`
- [ ] `bibtex`
- [ ] `BlogCatalog`
- [ ] `delicious`
- [ ] `ECtHR (A) (LexGLUE)`
- [ ] `ECtHR (B) (LexGLUE)`
- [ ] `EUR-LEX (LexGLUE)`
- [ ] `EUR-Lex`
- [ ] `EURLEX57K`
- [ ] `Flickr`
- [ ] `mediamill (exp1)`
- [ ] `PPI`
- [ ] `rcv1v2 (topics; subsets)`
- [ ] `rcv1v2 (topics; full sets)`
- [ ] `rcv1v2 (industries; full sets)`
- [ ] `rcv1v2 (regions; full sets)`
- [x] `scene-classification`
- [ ] `siam-competition2007`
- [ ] `UNFAIR-ToS (LexGLUE)`
- [ ] `Wiki10-31K`
- [ ] `yeast`
- [ ] `YouTube`

#### String data

- [ ] `mnist (string format)`

### Curated datasets

Package the original releases for distribution under `datamonger` on Zenodo
or another public host. Preserve source values, labels, missing values, and
any original partitions. Carry forward the attribution and terms of the
specific release used.

Gisette and Madelon already have curated releases.
[Gisette](curation/guyon2004-gisette/2/README.md),
[Madelon](curation/guyon2004-madelon/1/README.md).

#### UCI releases

UCI publishes these editions under CC BY 4.0.

- [ ] `abalone` (`uci:abalone@1` already fetches the original).
  [Abalone](https://archive.ics.uci.edu/dataset/1/abalone)
- [ ] `australian`.
  [Statlog Australian Credit Approval](https://archive.ics.uci.edu/dataset/143/statlog+australian+credit+approval)
- [ ] `breast-cancer`. Use the original Wisconsin records, including rows
  with missing values.
  [Breast Cancer Wisconsin (Original)](https://archive.ics.uci.edu/dataset/15/breast-cancer-wisconsin-original)
- [ ] `connect-4`. Use the board positions and their original labels.
  [Connect-4](https://archive.ics.uci.edu/dataset/26/connect%2B4)
- [ ] `german.numer`. Use Hofmann's original categorical file and its cost
  matrix.
  [Statlog German Credit Data](https://archive.ics.uci.edu/dataset/144/statlog+german+credit+data)
- [ ] `HIGGS`. Use the original simulated events.
  [HIGGS](https://archive.ics.uci.edu/dataset/280/higgs)
- [ ] `ionosphere`.
  [Ionosphere](https://archive.ics.uci.edu/dataset/52/ionosphere)
- [ ] `iris` (`uci:iris@1` already fetches the original).
  [Iris](https://archive.ics.uci.edu/dataset/53/iris)
- [ ] `letter`.
  [Letter Recognition](https://archive.ics.uci.edu/dataset/59/letter+recognition)
- [ ] `liver-disorders`. Keep the drinks-per-day measurement and the original
  split indicator as separate fields.
  [Liver Disorders](https://archive.ics.uci.edu/dataset/60/liver+disorders)
- [ ] `mpg`. Use all 398 Auto MPG records, including missing horsepower values.
  [Auto MPG](https://archive.ics.uci.edu/dataset/9/auto+mpg)
- [ ] `pendigits`.
  [Pen-Based Recognition of Handwritten Digits](https://archive.ics.uci.edu/dataset/81/pen+based+recognition+of+handwritten+digits)
- [ ] `phishing`. Use the original Phishing Websites features and labels.
  [Phishing Websites](https://archive.ics.uci.edu/dataset/327/phishing+websites)
- [ ] `poker`.
  [Poker Hand](https://archive.ics.uci.edu/dataset/158/poker)
- [ ] `pyrim`. Use the pyrimidines data from Ross King's release, which also
  includes `triazines`.
  [Qualitative Structure Activity Relationships](https://archive.ics.uci.edu/dataset/85/qualitative+structure+activity+relationships)
- [ ] `satimage`.
  [Statlog Landsat Satellite](https://archive.ics.uci.edu/dataset/146/statlog+landsat+satellite)
- [ ] `segment`.
  [Statlog Image Segmentation](https://archive.ics.uci.edu/dataset/147/statlog+image+segmentation)
- [ ] `Sensorless`.
  [Sensorless Drive Diagnosis](https://archive.ics.uci.edu/dataset/325/dataset+for+sensorless+drive+diagnosis)
- [ ] `shuttle`.
  [Statlog Shuttle](https://archive.ics.uci.edu/dataset/148/statlog+shuttle)
- [ ] `skin_nonskin`. Use the original color measurements and skin labels.
  [Skin Segmentation](https://archive.ics.uci.edu/dataset/229/skin+segmentation)
- [ ] `sonar`.
  [Sonar, Mines vs. Rocks](https://archive.ics.uci.edu/dataset/151/connectionist+bench+sonar+mines+vs+rocks)
- [ ] `SUSY`. Use the original simulated events.
  [SUSY](https://archive.ics.uci.edu/dataset/279/susy)
- [ ] `url`. Preserve the anonymized URL Reputation day files and labels.
  [URL Reputation](https://archive.ics.uci.edu/dataset/187/url+reputation)
- [ ] `vehicle`.
  [Statlog Vehicle Silhouettes](https://archive.ics.uci.edu/dataset/149/statlog+vehicle+silhouettes)
- [ ] `vowel`.
  [Deterding Vowel Recognition](https://archive.ics.uci.edu/dataset/152/connectionist+bench+vowel+recognition+deterding+data)
- [ ] `wine`. Use the cultivar recognition dataset.
  [Wine](https://archive.ics.uci.edu/dataset/109/wine)

#### Other releases

- [ ] `bodyfat`. Use Roger W. Johnson's StatLib deposit. A. Garth Fisher
  permits free distribution and noncommercial use.
  [StatLib data and terms](https://lib.stat.cmu.edu/datasets/bodyfat)
- [ ] `cod-rna`. Use the benchmark authors' unscaled feature tables and labels
  from Additional File 6 of their CC BY 2.0 paper.
  [Uzilov, Keegan, and Mathews](https://doi.org/10.1186/1471-2105-7-173)
- [ ] `criteo_tb`. Use Criteo's original 24 days of click logs under CC BY-NC-SA
  4.0. Choose a host with capacity for the full release.
  [Criteo terms](https://ailab.criteo.com/criteo-1tb-click-logs-dataset/),
  [Criteo Click Logs](https://huggingface.co/datasets/criteo/CriteoClickLogs)
- [ ] `ECtHR (A) (LexGLUE)` and `ECtHR (B) (LexGLUE)`. Use allegation and
  violation labels from AUEB's CC BY-NC-SA 4.0 release and match them to the
  official case IDs in HUDOC.
  [AUEB ECtHR cases](https://huggingface.co/datasets/AUEB-NLP/ecthr_cases),
  [Court reuse terms](https://www.echr.coe.int/copyright-and-disclaimer)
- [ ] `EUR-LEX (LexGLUE)`. Use the authors' `eurlex` release under CC BY 4.0
  and retain the EU terms for the underlying legal texts.
  [LexGLUE](https://huggingface.co/datasets/coastalcph/lex_glue),
  [EUR-Lex reuse terms](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html?locale=en)
- [ ] `EUR-Lex`. Assemble the English legal texts and EuroVoc labels directly
  from EUR-Lex. Use documents eligible for reuse and their CC0 metadata.
  [EUR-Lex reuse terms](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html?locale=en)
- [ ] `EURLEX57K`. Use the AUEB CLARIN deposit under CC BY-NC-SA 4.0.
  [EURLEX57K v1.0.0](https://inventory.clarin.gr/corpus/1112)
- [ ] `Hyperpartisan News Detection`. Use PAN's by-article annotations and
  source identifiers under CC BY 4.0.
  [PAN SemEval data](https://doi.org/10.5281/zenodo.1489920)
- [ ] `mg`. Generate a new time series from the original Mackey–Glass equation
  and publish the simulation parameters with the raw sequence.
  [Mackey and Glass](https://pubmed.ncbi.nlm.nih.gov/267326/),
  [Benchmark paper](https://doi.org/10.1023/A:1012474916001)
- [ ] `mnist` and `mnist (string format)`. Curate the raw QMNIST reconstruction
  as QMNIST, with its digit images and labels under the authors' BSD terms.
  [QMNIST](https://github.com/facebookresearch/qmnist)
- [ ] `SCOTUS (LexGLUE)`. Combine public-domain judicial opinions from the
  official U.S. Reports with the Supreme Court Database's issue-area labels
  under CC BY-NC 3.0 US.
  [Supreme Court opinions](https://www.supremecourt.gov/opinions/USReports.aspx),
  [SCDB releases and terms](http://scdb.wustl.edu/data.php)
- [ ] `Wiki-500K`. Compile English Wikipedia articles and categories from a
  pinned Wikimedia dump. Retain the revision IDs, attribution, and applicable
  CC BY-SA terms.
  [English Wikipedia dumps](https://dumps.wikimedia.org/enwiki/),
  [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use/en#7._Licensing_of_Content)

#### Already registered through LIBSVM

- [ ] `a1a` through `a9a`. Curate one Adult release from the original Census
  Income data under CC BY 4.0.
  [UCI Adult](https://archive.ics.uci.edu/dataset/2/adult)
- [ ] `cadata`. Assemble a California housing table directly from the public
  1990 Census block-group data.
  [Census Summary Tape File 3A](https://www2.census.gov/census_1990/1990STF3.html),
  [Census data rights](https://www2.census.gov/foia/ds_policies/ds027.pdf)
- [ ] `covtype` and `covtype-binary`. Curate the seven-class source under
  CC BY 4.0. Retain the original copyright notice.
  [UCI Covertype](https://archive.ics.uci.edu/dataset/31/covertype),
  [Original notice](https://archive.ics.uci.edu/ml/machine-learning-databases/covtype/covtype.info)
- [ ] `dna_scale` and `splice`. Curate the original three-class Primate
  Splice-junction Gene Sequences under CC BY 4.0.
  [UCI source](https://archive.ics.uci.edu/dataset/69/molecular+biology+splice+junction+gene+sequences)
- [ ] `glass_scale`. Use the original Glass Identification measurements under
  CC BY 4.0.
  [UCI Glass Identification](https://archive.ics.uci.edu/dataset/42/glass+identification)
- [ ] `heart_scale`. Use the original Statlog Heart records under CC BY 4.0.
  [UCI Statlog Heart](https://archive.ics.uci.edu/dataset/145/statlog+heart)
- [ ] `mushrooms`. Use the original categorical Mushroom data under CC BY 4.0.
  [UCI Mushroom](https://archive.ics.uci.edu/dataset/73/mushroom)
- [ ] `triazines_scale`. Use the triazines data from Ross King's CC BY 4.0
  release, which also includes `pyrim`.
  [UCI Qualitative Structure Activity Relationships](https://archive.ics.uci.edu/dataset/85/qualitative+structure+activity+relationships)
- [ ] `yearpredictionmsd`. Use the original audio features and artist-disjoint
  split under CC BY 4.0.
  [UCI Year Prediction MSD](https://archive.ics.uci.edu/dataset/203/yearpredictionmsd)

#### Redistribution rights to verify for registered datasets

- [ ] `colon-cancer` and `duke`. Confirm the source terms for the original
  Alon and West gene-expression tables.
  [Alon et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC21986/),
  [West et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC58752/)
- [ ] `e2006-log1p` and `e2006-tfidf`. Confirm onward sharing rights for the
  academic-use 10-K Corpus and the associated volatility targets.
  [CMU 10-K Corpus](https://www.cs.cmu.edu/~ark/10K/)
- [ ] `leukemia`. Confirm the rights to redistribute the expression and label
  tables from the author-attributed Bioconductor package separately.
  [golubEsets](https://bioconductor.org/packages/golubEsets/)
- [ ] `news20`, `news20-binary`, and `real-sim`. Confirm rights to the underlying
  Usenet posts or a release of the derived features. UCI's CC BY 4.0 listing
  covers its Twenty Newsgroups deposit and leaves the rights to individual
  posts unverified.
  [UCI Twenty Newsgroups](https://archive.ics.uci.edu/dataset/113/twenty+newsgroups),
  [SRAA](https://people.cs.umass.edu/~mccallum/data.html)
- [ ] `rcv1-binary`. Verify what the Reuters user agreement permits for
  downstream distribution of derived features and labels.
  [Reuters Corpus agreements](https://trec.nist.gov/data/reuters/reuters.html)
- [ ] `scene-classification`. Confirm terms for the original scene images or
  the published feature and label tables.
  [Boutell et al.](https://www.rose-hulman.edu/~boutell/publications/boutell04PRmultilabel.pdf)
- [ ] `w1a` through `w8a`. Identify a redistributable release of Platt's Web
  dataset.
  [LIBSVM provenance](https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/binary.html#w1a)
