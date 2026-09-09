# Changelog

## [0.2.0](https://github.com/jolars/datamonger/compare/datamonger-python-v0.1.0...datamonger-python-v0.2.0) (2026-09-09)

### Features
- publish first stable registry and specification (#7) ([`5d22864`](https://github.com/jolars/datamonger/commit/5d22864cd59002c5a74b85a781048b5c4c155807))

## [0.1.0](https://github.com/jolars/datamonger/compare/datamonger-python-v0.0.0...datamonger-python-v0.1.0) (2026-09-07)

### Features
- freeze revision 1 contracts ([`fdcd6fe`](https://github.com/jolars/datamonger/commit/fdcd6fe40f7e974366952bd0e284de001e1e730a))
- publish candidate registry ([`d5afe43`](https://github.com/jolars/datamonger/commit/d5afe43c5f6e52b0717dca73ea996f1830356e1b))
- curate candidate datasets ([`7a577af`](https://github.com/jolars/datamonger/commit/7a577af1059b21a522ee24ad23f36e79a6b7883c))
- add upstream canary ([`8c78022`](https://github.com/jolars/datamonger/commit/8c7802234a4f34ff630f81abd336d16643c1e460))
- add manifest authoring tool ([`99dbe00`](https://github.com/jolars/datamonger/commit/99dbe00245ff0248f69e5951e90e14d3885c2e93))
- complete Python decoding milestone ([`bba391c`](https://github.com/jolars/datamonger/commit/bba391c6ab9a186b384d8d572b44909c8c10f92e))
- stabilize Python return types ([`665b469`](https://github.com/jolars/datamonger/commit/665b469883e72ffd6e8fde37161c4bf9e01afe35))
- complete LIBSVM conformance ([`292df84`](https://github.com/jolars/datamonger/commit/292df84c69263178e1e102c60abff0d98c784601))
- complete delimited-text conformance ([`9a69450`](https://github.com/jolars/datamonger/commit/9a6945025912ca65f184a1dc1ec58a5550ffc44f))
- complete semantic error taxonomy ([`b3e26fc`](https://github.com/jolars/datamonger/commit/b3e26fc959cf25543cd4a920f6dc7e2185c528ba))
- add offline cache management ([`7a7b882`](https://github.com/jolars/datamonger/commit/7a7b882ef7ca774f240b00b737498b9026f4ff28))
- add concurrent cache leases ([`f08f109`](https://github.com/jolars/datamonger/commit/f08f1096bc272f4eac4f4715bace821adc133a58))
- complete HTTP retrieval semantics ([`0449429`](https://github.com/jolars/datamonger/commit/0449429a51619fe4115234c926f8ae2207ba4339))
- add artifact retrieval API ([`7cd54a7`](https://github.com/jolars/datamonger/commit/7cd54a7d45e63344b5933a5f03b27dcb69c9b067))
- add registry catalog lookup ([`881cd66`](https://github.com/jolars/datamonger/commit/881cd66b222c4d02f3176f0a6e7578e67665a404))
- support scoped registry selectors ([`34649b8`](https://github.com/jolars/datamonger/commit/34649b87d86bf7cee996884b02085a7f8e431074))
- bundle default registry snapshot ([`4f17c7c`](https://github.com/jolars/datamonger/commit/4f17c7c7c3fed801b4f9ee685180c73ece886e11))
- complete specification registry milestone ([`8d25760`](https://github.com/jolars/datamonger/commit/8d25760caf38d6281d57585514fad813df15cf35))
- complete sparse vertical proof ([`1af37bc`](https://github.com/jolars/datamonger/commit/1af37bc632ebc23c3a79b19cdf522cd98106e165))
- build Python CSV vertical slice ([`ca1e6d7`](https://github.com/jolars/datamonger/commit/ca1e6d77995afe4f0b9fa485ee8e1d9bc743c708))

### Bug Fixes
- validate manifests at registry build time ([`0ad7d89`](https://github.com/jolars/datamonger/commit/0ad7d896ebf42c59dea71ed38266b6072b10534b))
- harden retrieval and registry validation ([`f265a8a`](https://github.com/jolars/datamonger/commit/f265a8a830ab372ff31692ad83f34fb453fc869d))
- enforce explicit delimited-text record grammar ([`a7a8a38`](https://github.com/jolars/datamonger/commit/a7a8a38f8acb2ec797638d14720aff2bf76815e1))
- declare Ruff for CI ([`2f03c6c`](https://github.com/jolars/datamonger/commit/2f03c6c8702f583db014d6b582ae17426c805021))

### Performance Improvements
- store logical vectors unboxed ([`3b66850`](https://github.com/jolars/datamonger/commit/3b66850681f55a39b3019f6d8045127710be6bc9))
- hash sparse matrices from unboxed arrays ([`68fe671`](https://github.com/jolars/datamonger/commit/68fe6716a2c20c7396982a4f8afd13f09ad0010e))
