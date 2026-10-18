# Citation metadata extension

This extension introduces manifest schema version 2 and index schema version 2.
The frozen revision 1 schemas, dataset identity, decoders, canonical form,
selectors, release sources, and catalogs retain their existing contracts.

## Manifest records

Manifest version 2 adds two optional provenance fields:

- `citations`: an ordered array of reference records.
- `citation_instructions`: nonempty text recording the upstream provider's
  citation instructions, including requests to cite several references together.

Each reference requires a nonempty `citation` string containing curated citation
text. Optional fields are:

- `role`: `dataset` for the data or a deposit, `paper` for an associated
  publication, or `collection` for a distributing collection or benchmark.
- `note`: nonempty text explaining the reference's relevance.
- `recommended`: a boolean recording whether upstream recommends citing this
  reference. Omission means the recommendation has not been recorded.

Roles describe references; they do not imply citation recommendations. Several
references may be recommended together. Preserve upstream instructions and
reference order. Do not infer a recommendation from a role, DOI, or the presence
of a reference. Unknown roles may be left unspecified and explained in a note.

For example, this hypothetical provenance fragment requests two citations:

```yaml
citations:
  - citation: "Authors. Dataset title. Versioned deposit."
    role: dataset
    recommended: true
  - citation: "Authors. Paper describing data collection."
    role: paper
    note: Describes how the observations were collected.
    recommended: true
  - citation: "Authors. Benchmark collection."
    role: collection
    recommended: false
citation_instructions: Cite the deposit and the collection paper together.
```

The legacy `provenance.citation` string remains valid. A provenance object must
not contain both `citation` and `citations`. Clients expose a legacy string as
one reference containing only `citation`; its role and recommendation remain
unknown. Missing citations and an empty `citations` array both represent an
absence of citation metadata. Missing metadata does not prevent retrieval.

Citations are descriptive metadata. Corrections require a new registry release,
but do not require a new dataset version.

## Registry compatibility

Index version 1 continues to accept only manifest version 1. Index version 2
accepts manifests of versions 1 and 2. The registry builder emits index version 2
when any selected manifest uses version 2; otherwise it retains version 1.
Release-source version 1 continues to identify manifests by path and needs no new
fields. Selectors and catalogs retain version 1 independently of index versions.
Clients must reject unsupported schema versions before interpreting their fields.
Published indexes and selectors remain immutable.

## Client behavior

Python, R, and Julia expose `cite_data()` with the same dataset resolution,
registry selection, and offline behavior as `data_info()`. It retrieves registry
metadata only and never downloads dataset artifacts or resolves bibliographic
identifiers through another service.

By default, the helper selects references with `recommended: true` whenever any
reference carries a recommendation flag. If none carries a flag, it returns all
references and text output explicitly says that no upstream recommendation is
recorded. If flags exist but none is true, the default selection is empty.
`include_all` requests every reference, regardless of flags.

The default `format="text"` returns citation text with optional role labels,
notes, and upstream instructions. Missing citations and an empty recommendation
selection produce explicit messages. `format="records"` returns selected
reference records with optional fields preserved, including the distinction
between an absent recommendation and `false`. Bibliography export is outside
this extension.

`data_info()` and fetch results requested with `return_info` expose all reference
records as `citations` and upstream instructions as `citation_instructions`.
Missing instructions are `None`, `NULL`, or `nothing`. The enclosing metadata
identifies the resolved dataset version and exact registry release and digest.
Fetch metadata comes from the same record used for retrieval, without a second
registry lookup. The default data return types remain unchanged.
