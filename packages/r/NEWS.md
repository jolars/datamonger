# datamonger 0.3.0

## Features

- fetch sparse label joins in R ([`10bf049`](https://github.com/jolars/datamonger/commit/10bf0491627818e10965aa9aca0d0e50c8025b88))
- bundle registry 1.7.0 (#74) ([`ec6d033`](https://github.com/jolars/datamonger/commit/ec6d0331ba80541737bedaf8a96207461529cafe))
- fetch graphs and hypergraphs in R ([`09c325f`](https://github.com/jolars/datamonger/commit/09c325fb9ddd823acaaa61a9cc5113c21a0383f9))
- **r:** update datamonger_core to 0.4 ([`40d5c50`](https://github.com/jolars/datamonger/commit/40d5c500af707fa80333da91cdff8bbe8bd4ba48))

# datamonger 0.2.0

## Features

- bundle registry 1.6.0 (#61) ([`a06f5af`](https://github.com/jolars/datamonger/commit/a06f5aff52d81f710c4342e50aa12d26767ba68f))
- bundle registry 1.5.0 (#50) ([`fdd31af`](https://github.com/jolars/datamonger/commit/fdd31af49564d01450fe3af5f6d28d4cf4259557))
- fetch SVMLight ranking datasets in R ([`bdfaced`](https://github.com/jolars/datamonger/commit/bdfacedbd31eefd6294ac421a6dfd32da6fcdf98))
- fetch multilabel LIBSVM datasets in R ([`1403eb0`](https://github.com/jolars/datamonger/commit/1403eb0cfd36f9b6287efa01bd14e219d6e5866a))
- fetch semicolon-delimited datasets in R ([`9df4e6c`](https://github.com/jolars/datamonger/commit/9df4e6c4bbcba2830be1bc31167a40e88a5ad5f0))

## Bug fixes

- isolate staged R adapter workspace ([`ec130e5`](https://github.com/jolars/datamonger/commit/ec130e56e3ff4c8feabb4b26a9879a05a2190be3))

## Performance improvements

- skip NA assignment for complete R columns ([`6cc1bc2`](https://github.com/jolars/datamonger/commit/6cc1bc2b1b0c5bc92f6cab0d19d73dbeca041be7))

# datamonger 0.1.0

## Features

- bundle registry 1.4.0 (#27) ([`cbce1ad`](https://github.com/jolars/datamonger/commit/cbce1ade915e61aede10d65d8d0fa16169e94a11))
- **registry:** add Madelon with LIBSVM decoder v2 ([`9b07dd2`](https://github.com/jolars/datamonger/commit/9b07dd2196037442ea0bbd88ef2c3bed7dc212da))
- bundle registry 1.3.0 (#22) ([`ea697d3`](https://github.com/jolars/datamonger/commit/ea697d377befc316983d3294bb7880de95ace527))
- support named dataset splits ([`72dbdf9`](https://github.com/jolars/datamonger/commit/72dbdf9f489934218867f5c69d665448363d853e))
- **registry:** record preprocessing metadata ([`c10b300`](https://github.com/jolars/datamonger/commit/c10b30057163e9e062e8a78ba534d19f161d1896))
- add Rust core and migrate R backend ([`510c863`](https://github.com/jolars/datamonger/commit/510c8631bd8c063454d933d3998fe8f878a02dc1))
- add dataset citations and `cite_data()` ([`33c2805`](https://github.com/jolars/datamonger/commit/33c280542886c1a4d1c8a14dc7664b647d96e138))
- bundle registry 1.2.0 (#17) ([`bebb89d`](https://github.com/jolars/datamonger/commit/bebb89d6f2f43b4d4f58d1e54574b268d8fd633e))
- automate registry bundle update PRs ([`c1e587b`](https://github.com/jolars/datamonger/commit/c1e587b6ef9189dbeebf4d3545689790449df566))
- bundle stable registry in all clients ([`1ea6a3e`](https://github.com/jolars/datamonger/commit/1ea6a3e122c617b32515ced7f1f6aa65cfca5421))
- support qualified dataset references ([`3e9fbce`](https://github.com/jolars/datamonger/commit/3e9fbcec1ed403e32a35cf68758555421c702c19))
- publish first stable registry and specification (#7) ([`5d22864`](https://github.com/jolars/datamonger/commit/5d22864cd59002c5a74b85a781048b5c4c155807))
- default to use cache ([`5d2ae74`](https://github.com/jolars/datamonger/commit/5d2ae74d735ae3abb974ff720cd2269a4606c224))
- add R client ([`d007bc0`](https://github.com/jolars/datamonger/commit/d007bc0e501e2979fe24bacdaf28b92d052e7159))

## Bug fixes

- disable LTO for Windows R helper ([`92b4daa`](https://github.com/jolars/datamonger/commit/92b4daacf8a946e882d8941cba9cb26e152850d3))
- shorten Windows R build paths ([`14999e4`](https://github.com/jolars/datamonger/commit/14999e41fc36dbcfd4642f424be2a655216eb0b8))
- **r:** compress the bundled catalog ([`b74ce81`](https://github.com/jolars/datamonger/commit/b74ce8136f000916d88d0cbe8e5561de4e54fb7a))
- **r:** compress the bundled catalog ([`2adf7e7`](https://github.com/jolars/datamonger/commit/2adf7e7bcb5f3f8e2882d13d41d1b07e32eddb79))
- stop generating R dependency license notices ([`e4d904d`](https://github.com/jolars/datamonger/commit/e4d904daa797c4c98d64ab4e0adad9e0f22046ad))
- restore vendored Rust license notices ([`5ed00db`](https://github.com/jolars/datamonger/commit/5ed00dbdb6070a48e6149c6208a75adff98b0130))
- preserve the R adapter core dependency ([`5e9523b`](https://github.com/jolars/datamonger/commit/5e9523b650d13d6e2c1374a2de86a50f25026c3e))
