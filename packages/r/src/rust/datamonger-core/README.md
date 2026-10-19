# datamonger-core

Strict decoding and canonical verification for Datamonger specification revision
1. The crate supports CSV, TSV, LIBSVM, split LIBSVM, gzip, and bzip2 artifacts.
It has no dependency on R, Python, Julia, registry services, or client caches.

```rust
use datamonger_core::{canonical_sha256, decode_libsvm, LabelType, LibsvmOptions};

let options = LibsvmOptions {
    feature_count: 3,
    label_type: LabelType::Int64,
    target_name: "response".into(),
};
let components = decode_libsvm(&b"+1 1:0.5 3:2\n"[..], &options)?;
let digest = canonical_sha256(&components)?;
# Ok::<(), datamonger_core::Error>(())
```

Readers operate incrementally, retaining typed result buffers rather than the
complete input text. Canonical hashing emits bounded chunks without a second
serialized copy. `write_canonical()` also accepts an ordinary `std::io::Write`
sink. Functions ending in `_with_control` accept cancellation checkpoints.

The minimum supported Rust version is 1.82. The crate uses Rust compression
backends and follows the repository's MIT license. It is prepared for future
crates.io publication; no release has been published yet.

The versioned contracts under `spec/` in the Datamonger repository are
authoritative. Tests carry a synchronized copy of the shared conformance corpus
so they also run from the packaged crate.
