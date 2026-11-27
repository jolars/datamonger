# Changelog

## [0.5.0](https://github.com/jolars/datamonger/compare/datamonger-core-v0.4.0...datamonger-core-v0.5.0) (2026-11-27)

### Features

- decode sparse label joins ([`21c23d2`](https://github.com/jolars/datamonger/commit/21c23d2de621e4d2d99a82e5f46feb1dfff67502))

## [0.4.0](https://github.com/jolars/datamonger/compare/datamonger-core-v0.3.0...datamonger-core-v0.4.0) (2026-11-20)

### Features

- add graph and hypergraph decoding to Rust core ([`d716ad9`](https://github.com/jolars/datamonger/commit/d716ad95c3f13f7860155db5475da3c8560d1f90))
- support delimited text preambles and headerless input ([`82e4089`](https://github.com/jolars/datamonger/commit/82e4089349930ca4f35ffadde9222676429e1081))

## [0.3.0](https://github.com/jolars/datamonger/compare/datamonger-core-v0.2.0...datamonger-core-v0.3.0) (2026-11-19)

### Features

- decode semicolon-delimited CSV ([`cbb63e0`](https://github.com/jolars/datamonger/commit/cbb63e055a1c36317ce0bcea585bb492ab545fba))

### Performance Improvements

- speed up CSV decoding and benchmark against `csv` ([`9a6ec62`](https://github.com/jolars/datamonger/commit/9a6ec623d2eb9cd83acffb6a9204f07b83377347))
- borrow delimited fields from the input record ([`7407312`](https://github.com/jolars/datamonger/commit/7407312acef88885410d9d499e5adca7c100d847))
- parse LIBSVM feature indices in one pass ([`aca4879`](https://github.com/jolars/datamonger/commit/aca48794e41094e837b20726db79bbf2d7ff8e8e))
- scan LIBSVM delimiters as bytes ([`75d5952`](https://github.com/jolars/datamonger/commit/75d59524f161f94f2f91134265ffdca6d80e412e))

## [0.2.0](https://github.com/jolars/datamonger/compare/datamonger-core-v0.1.0...datamonger-core-v0.2.0) (2026-10-27)

### Features
- **registry:** add Madelon with LIBSVM decoder v2 ([`9b07dd2`](https://github.com/jolars/datamonger/commit/9b07dd2196037442ea0bbd88ef2c3bed7dc212da))
- support named dataset splits ([`72dbdf9`](https://github.com/jolars/datamonger/commit/72dbdf9f489934218867f5c69d665448363d853e))
- migrate Julia decoding to native core (#19) ([`3b7b4c0`](https://github.com/jolars/datamonger/commit/3b7b4c00ba8b785c5e887fa34385c7775d5836ff))
- **python:** use the native decoding core ([`6985816`](https://github.com/jolars/datamonger/commit/6985816163d93eac2a0246d1d086226e132c052d))
- **registry:** record preprocessing metadata ([`c10b300`](https://github.com/jolars/datamonger/commit/c10b30057163e9e062e8a78ba534d19f161d1896))
- add Rust core and migrate R backend ([`510c863`](https://github.com/jolars/datamonger/commit/510c8631bd8c063454d933d3998fe8f878a02dc1))
