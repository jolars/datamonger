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
- [x] `url`. Preserve the anonymized URL Reputation day files and labels.
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
- [ ] `leukemia`. Confirm redistribution rights for the normalized LIBSVM
  files. The `Golub1999` task below uses a separate source release.
  [LIBSVM Leukemia](https://www.csie.ntu.edu.tw/~cjlin/libsvmtools/datasets/binary.html#leukemia)
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

#### Iowa Biostatistics

Use the source editions linked below and retain their attribution and reuse
terms. Iowa's teaching files identify the studies and any transformations.
[Iowa Biostatistics catalog](https://iowabiostat.github.io/data-sets/),
[reviewed source revision](https://github.com/IowaBiostat/data-sets/tree/f6b782b919a76898dbc1f0421e96274ef6987b6d)

Four studies already have curated releases.
[`brca1`](curation/brca1/1/README.md),
[`Koussounadis2014`](curation/koussounadis2014/1/README.md),
[`Rhee2006`](curation/rhee2006/1/README.md), and
[`Scheetz2006`](curation/scheetz2006/1/README.md).

##### Source editions and published tables

- [ ] `anorexia`. Use the 72-record `MASS` release under GPL-2 or GPL-3 and
  credit the source identified in its documentation.
  [MASS](https://cran.r-project.org/package=MASS),
  [Dataset documentation](https://stat.ethz.ch/R-manual/R-devel/library/MASS/html/anorexia.html)
- [ ] `britdoc`. Transcribe the published coronary death counts and
  person-years by age group and smoking status.
  [IARC Table 3.15](https://publications.iarc.who.int/_publications/media/download/3498/937cfe25cb8e0db60372d30690ecbd7b78698eef.pdf),
  [British Doctors' Study](https://www.ctsu.ox.ac.uk/research/british-doctors-study)
- [ ] `cirrhosis`. Use the study investigators' Mayo Clinic trial data as
  released by UCI under CC BY 4.0.
  [UCI Cirrhosis](https://archive.ics.uci.edu/dataset/878/primary%2Bbiliary%2Bcirrhosis)
- [ ] `corn`. Transcribe the 15 cross-fertilized and self-fertilized maize
  pairs from Darwin's public-domain Table VII.
  [Darwin's 1876 study](https://darwin-online.org.uk/converted/published/1876_CrossandSelfFertilisation_F1249/1876_CrossandSelfFertilisation_F1249.html)
- [ ] `covid-states`. Build the state summaries from the New York Times death
  counts, Oxford's state policy data, and Census population estimates. The
  Times permits noncommercial derivatives under its data terms. Oxford's
  release is CC BY 4.0.
  [Source recipe](https://github.com/IowaBiostat/data-sets/blob/main/covid-states/data.r),
  [NYT terms](https://github.com/nytimes/covid-19-data/blob/master/LICENSE),
  [Oxford license](https://github.com/OxCGRT/USA-covid-policy/blob/master/LICENSE.txt)
- [ ] `Freireich1963` and `Nahman1992`. Use `drug6mp` and `kidney` from the
  textbook authors' GPL-3-or-later `KMsurv` release. Verify the Freireich
  follow-up unit against the original trial before export.
  [KMsurv](https://github.com/jun-yan/KMsurv),
  [Freireich trial](https://doi.org/10.1182/blood.v21.6.699.699)
- [ ] `Golub1999`. Use the expression measurements and diagnosis labels from
  the Todd Golub–credited `golubEsets` data package under LGPL. Keep the
  documented study partitions and select fields with known provenance.
  [Bioconductor release](https://bioconductor.org/packages/golubEsets/)
- [ ] `Hoel1972`. Use the 181-mouse `hoel` table from the LGPL-2-or-later
  `survival` release.
  [Dataset documentation](https://github.com/therneau/survival/blob/master/man/hoel.Rd),
  [Package terms](https://github.com/therneau/survival/blob/master/DESCRIPTION)
- [ ] `infmort`. Use the country rates and their reference years from
  UNICEF's 2019 statistical tables under CC BY 3.0 IGO.
  [UNICEF Table 2 and terms](https://data.unicef.org/resources/dataset/sowc-2019-statistical-tables/)
- [ ] `inhaler`. Transcribe the published crossover trial frequencies as
  aggregate counts by treatment order and response.
  [Ezzet and Whitehead](https://doi.org/10.1002/sim.4780100611),
  [Frequency table documentation](https://www.multibugs.org/examples/latest/Inhalers.html)
- [ ] `lister`. Transcribe the published counts by surgical period, retaining
  the original years and amputation groups where available.
  [Public-domain Lister report](https://wellcomecollection.org/works/y85njhwf/items)
- [ ] `mortality`. Use the constructed United States deaths series by age,
  year, and sex under CC BY 4.0.
  [U.S. series](https://www.mortality.org/Country/Country?cntr=USA),
  [HMD terms for constructed data](https://www.mortality.org/Data/UserAgreement)
- [ ] `nhanes-am`, `nhanes-aw`, and `lipids`. Use the 2005–2006 public-use
  demographic, body measurement, and lipid files. Carry forward CDC's
  statistical-use and confidentiality terms.
  [NHANES 2005–2006](https://wwwn.cdc.gov/nchs/nhanes/search/DataPage.aspx?Cycle=2005-2006),
  [CDC reproduction and citation terms](https://wwwn.cdc.gov/Nchs/Nhanes/Nhanescitation.Aspx),
  [Data user agreement](https://www.cdc.gov/nchs/policy/data-user-agreement.html)
- [ ] `pearson`. Transcribe Pearson and Lee's public-domain Table XXII as
  grouped father-son height frequencies, including the fractional counts.
  [Original paper](https://doi.org/10.1093/biomet/2.4.357),
  [Table scan](https://pages.uoregon.edu/dlevin/DATA/ROS-Examples-master/PearsonLee/figs/PearsonLee1903.pdf)
- [ ] `pollution`. Use the city-level table `ex1217` from Ramsey and Schafer's
  GPL-2-or-later data package after confirming the terms for the original
  compilation. Credit the original study.
  [Sleuth3](https://cran.r-project.org/package=Sleuth3),
  [McDonald and Schwing](https://doi.org/10.1080/00401706.1973.10489073)
- [ ] `Sachs2005`. Use the measured flow-cytometry data and intervention
  labels under the authors' CC BY 4.0 grant.
  [Licensed release](https://zenodo.org/records/7681811)
- [ ] `Scholtens2004`. Use the eight original arrays and design from the
  study coauthors' LGPL `estrogen` data package.
  [Bioconductor release](https://bioconductor.org/packages/estrogen/)
- [ ] `spam`. Use the original 4,601-record UCI Spambase release under
  CC BY 4.0.
  [UCI Spambase](https://archive.ics.uci.edu/dataset/94/spambase)
- [ ] `titanic`. Transcribe the class, age, sex, and survival counts from the
  1912 British inquiry report. Crown copyright has expired.
  [Inquiry report](https://www.titanicinquiry.org/BOTInq/BOTReport/botRepSaved.php),
  [Crown copyright terms](https://www.nationalarchives.gov.uk/information-management/re-using-public-sector-information/crown-copyright-faqs/)
- [ ] `warming`. Use NASA's public-domain GISTEMP global land-ocean temperature
  anomalies and record the version and retrieval date.
  [GISTEMP v4 tables](https://data.giss.nasa.gov/gistemp/data_v4.html),
  [NASA source statement](https://science.nasa.gov/earth/climate-change/the-raw-truth-on-global-temperature-records/)
- [ ] `whickham`. Transcribe the published smoking and survival counts by
  age group as aggregate facts.
  [Appleton et al.](https://doi.org/10.1080/00031305.1996.10473563),
  [Teaching dataset provenance](https://www.mosaic-web.org/mosaicData/reference/Whickham.html)
- [x] `Yeoh2002`. Use the processed study measurements and labels from the
  archived LGPL-2-or-later `stjudem` data package.
  [Bioconductor archive](https://mirrors.nju.edu.cn/bioconductor/packages/3.5/data/experiment/html/stjudem.html)

##### GEO source editions

Use the deposited measurements and documented study labels. Apply GEO's
qualified redistribution policy and review accession-specific notices.
[GEO source terms](https://www.ncbi.nlm.nih.gov/geo/info/disclaimer.html)

- [ ] `glioma`. Use the Bredel glioblastoma copy-number measurements for
  GBM29 and GBM31, retaining the samples and chromosome coordinates.
  [GSE1991](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE1991),
  [Benchmark provenance](https://tibshirani.su.domains/ftp/fusedLassoCGH.pdf)
- [ ] `Gode2011`. Review the source accession for the study's deposited
  measurements. Iowa uses a subset of the deposit.
  [GSE18763](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE18763)
- [ ] `Ramaswamy2001`. Use the NCI caArray migration and record the specimen
  and platform selection.
  [GSE68928](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE68928)
- [ ] `Scherzer2007`. Use the authors' blood expression study and diagnostic
  labels.
  [GSE6613](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE6613)
- [ ] `Shedden2008`. Use the migrated NCI Director's Challenge archive and
  preserve missing outcomes in the source cohort.
  [GSE68465](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE68465)

##### Teaching simulations

- [ ] `nhanes-subsamples`. Generate new sampling distributions from the
  2005–2006 public-use triglyceride measurements and record the sample sizes
  and seed.
  [CDC lipid files](https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2005/DataFiles/TRIGLY_D.htm)
- [ ] `Samaha2003`. Generate new synthetic triglyceride measurements from
  the published trial summaries and document the simulation assumptions.
  [Samaha et al.](https://doi.org/10.1056/NEJMoa022637)
- [ ] `tdap`. Generate a new synthetic teaching dataset informed by the
  published obstetric outcome summaries. Document the simulation assumptions.
  [Kharbanda et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC6599584/)

##### Redistribution rights to verify

- `Byar1980`, `support`, and `whoari`. Vanderbilt gives permission to use
  these datasets. Confirm that it covers republication of the proposed
  clinical extracts. UCI refers SUPPORT2 users to the source terms.
  [Vanderbilt terms](https://hbiostat.org/data/),
  [UCI SUPPORT2](https://archive.ics.uci.edu/dataset/880/support2)
- `cholostyramine`, `glcamd`, and `parkinsons`. Confirm rights for the
  teaching extracts. The original cholesterol trial and Parkinson's genetics
  data have controlled-access releases. The glaucoma recipe cites local
  patient-level files.
  [NHLBI trial](https://biolincc.nhlbi.nih.gov/studies/lrccppt/),
  [Glaucoma recipe](https://github.com/IowaBiostat/data-sets/blob/main/glcamd/x.r),
  [Parkinson's dbGaP study](https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=phs000196)
- `allergen`, `anemia`, `diarrhea`, `gvhd`, `hypercalcemia`, `infant-heart`,
  `lead-iq`, `Podzielinski2012`, `Scrucca2010`, and `tailgating`. Identify
  authorized releases of the participant-level tables. The known sources
  are study reports, teaching extracts, or local study files.
  [Iowa catalog and study references](https://iowabiostat.github.io/data-sets/)
- `cystic-fibrosis`, `fetal-lamb`, `flicker`, `lip-cancer`, `nerve`,
  `oatbran`, `Pike1966`, and `tips`. Verify the source edition and the
  rights for the measurements carried by textbook, software, or teaching
  collections.
  [Iowa catalog and source references](https://iowabiostat.github.io/data-sets/)
- `fumarate`. Locate a release or permission from the St. Clair lab for
  the unpublished measurements.
  [Iowa source note](https://iowabiostat.github.io/data-sets/fumarate/fumarate.html)
- `hedenfalk` and `Singh2002`. Recover the NHGRI supplement and the Broad
  Institute expression release, respectively, and verify their terms and
  study provenance.
  [Hedenfalk source note](https://iowabiostat.github.io/data-sets/hedenfalk/hedenfalk.html),
  [Singh source note](https://iowabiostat.github.io/data-sets/Singh2002/Singh2002.html)
- `sids`. Review republication of the infant-level fields in the original
  study's Table 1, including whether the proposed extract preserves privacy.
  [Walker et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC1647245/)
- `tukey`. Obtain permission for the Alfred Eisenstaedt LIFE photograph
  used to generate the pixel matrix.
  [LIFE Picture Collection](https://www.life.com/life-picture-collection/)
