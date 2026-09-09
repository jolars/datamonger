# Registry 2026.09 certification

Registry `2026.09` is the first stable registry, paired with specification
release `spec-v1`. Its sole GitHub Release asset is `index.json`.

| Release | Index SHA-256 |
| --- | --- |
| Certified candidate `candidate-0002` | `3eee3e1cb6730d73d3a2a1f251d693b17f4e8c3fc520ebf256b4304ac82584c6` |
| Stable registry `2026.09` | `4c1676acbd8c1164d900161605b60da5b04503e633620230185254a7beff7d61` |

The [strong selector](selector.json) names the stable index URL. The generated
stable index equals the certified candidate index with only its top-level
`release` changed. All ten dataset records, artifact locations, defaults,
component expectations, and canonical verification records are unchanged.
The registry builder checks evolution against every earlier release, and a
regression test asserts this exact promotion relationship and the fixed digest.

## Review and independent reproduction

Johan Larsson recorded the provenance and licensing review in commit
[`87f85e3`](https://github.com/jolars/datamonger/commit/87f85e3040fad7106684a28ed1ce247c9f853644)
and completion of independent reproduction and review in commit
[`1b9e854`](https://github.com/jolars/datamonger/commit/1b9e85496724a63579de887121ae8b7f82819403).
Promotion retains those reviewed records without introducing new artifacts or
interpretations.

The publication audit on September 9, 2026, uses the Python, R, and Julia
implementations from commit
[`93dc641`](https://github.com/jolars/datamonger/commit/93dc641d8ff5adffe607b93731cc2ce22ef58fb4).
The release preparation changes only the registry selection argument in the
independent live-audit scripts; decoding and canonical implementations are
unchanged. R and Julia compute canonical digests independently of Python.

`devenv test` passes the complete hermetic quality gate, including all three
client suites, shared conformance fixture synchronization, generated registry
checks, Python formatting, linting, typing, and distribution builds, and the
CRAN-style R check. The local gate uses Python 3.14.7, R 4.6.1, and Julia 1.12.7.
No normative contract semantics or conformance cases changed after
`spec-v1-rc1`; `spec-v1` freezes the same version 1 inventory.

The live candidate audit retrieves the published digest-selected index and
upstream bytes using fresh caches. Python 3.11.13, R 4.6.1, and Julia 1.12.7
reproduce all ten verification records:

| Dataset | Canonical SHA-256 |
| --- | --- |
| `libsvm:cadata@1` | `63e4b305e1f12480287b7e5202a34537c804035140bc9d4f782972beed86c82f` |
| `libsvm:colon-cancer@1` | `b1a66886cbdc0200faef4a3b70efa7956ef0eaddf0ec6eb516e390ff0640ec4f` |
| `libsvm:dna_scale@1` | `75b61a9bb5c15ec6b94d80bb1888a0e75cb399d8313d0b2bf031983d6e156c5c` |
| `libsvm:glass_scale@1` | `efc28baf54fe4ddc317738ab41e4fdf99958c09e9b40fec202d244c5630a55e2` |
| `libsvm:heart_scale@1` | `93d97aa1b3775ab6a48fc4f8897cef8efdc7483511df1fb89c397397da107d03` |
| `uci:abalone@1` | `99d926b369b8e14604f120eb38ea909251cafdd44f3681277ab96e573166c875` |
| `uci:breast-cancer-wisconsin-diagnostic@1` | `8edb29f96f043f66a9da79f5bd911c700c4ed49ae32c78bbc53cc9f066c711ce` |
| `uci:iris@1` | `cfa2a70911157e2d7072fe97ce29edf0a7c998e5d6b3312b758998621427e212` |
| `uci:wholesale-customers@1` | `ec35167809b9182b72c0f6ff4f66ce07def4da896b60ee59d52c7c0ca9816c3f` |
| `uci:wine-quality@1` | `07c0d3702de1c6d101a44e856801a2b428e56edfb4a215a5753ac359363be62a` |

The [operations runbook](../../../OPERATIONS.md#stable-release-gate) records the
commands for repeating all three audits against the published stable selector.

## Published release verification

Both [`registry-2026.09`](https://github.com/jolars/datamonger/releases/tag/registry-2026.09)
and [`spec-v1`](https://github.com/jolars/datamonger/releases/tag/spec-v1) are
published as stable releases at commit `5d22864cd59002c5a74b85a781048b5c4c155807`.
The [release PR CI run](https://github.com/jolars/datamonger/actions/runs/34324309381)
passed Python, R, and both Julia versions (1.10 and current).
The [publication workflow](https://github.com/jolars/datamonger/actions/runs/34324802623)
downloaded the published index, verified its digest, and passed all 22 canary
checks.

Fresh local audits against the published `2026.09` selector also passed in
Python 3.11.13, R 4.6.1, and Julia 1.12.7, reproducing every digest in the table
above. The downloaded asset is byte-identical to the checked-in index, and
`resolve_registry("2026.09")` returns the exact checked-in selector. An explicit
stable-selector Iris fetch returns a verified 150-row, five-column data frame.

## Limitations

The registry is unsigned, and all artifacts remain upstream-only. Stable
certification establishes cross-language agreement on the registered logical
values; it does not establish scientific suitability or preserve upstream data.
LIBSVM entries with unknown license status retain that status and their existing
evidence. No dataset artifacts are redistributed by this release.

On the audit host, Python 3.14.7 rejects the certificate chain served by
`www.csie.ntu.edu.tw` with `CERTIFICATE_VERIFY_FAILED: Missing Subject Key
Identifier`. This prevents live retrieval of `cadata`, `colon-cancer`,
`dna_scale`, and `glass_scale` on that runtime. Python 3.11, R, and Julia retrieve
and verify the same registered bytes successfully. Python enabled stricter
default X.509 validation in 3.13; see the
[Python SSL documentation](https://docs.python.org/3/library/ssl.html#ssl.create_default_context).
No TLS verification settings are weakened. The release and scheduled canaries
use Python 3.11, matching the existing CI baseline. Upstream certificate repair
or a later reviewed registry location update is needed for affected runtimes.

Client packages still bundle `proof-0001`. Users can select `2026.09` explicitly
before the subsequent coordinated client releases adopt the stable snapshot.
