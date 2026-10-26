//! Strict, streaming implementations of Datamonger revision 1.
//!
//! This crate decodes verified artifacts into language-independent buffers and
//! writes the canonical verification stream without materializing another copy
//! of the dataset. Retrieval, registry selection, and caching belong to clients.
//!
//! ```
//! use datamonger_core::{canonical_sha256, decode_libsvm, LabelType, LibsvmOptions};
//! let options = LibsvmOptions {
//!     feature_count: 3,
//!     label_type: LabelType::Int64,
//!     target_name: "response".into(),
//! };
//! let components = decode_libsvm(&b"+1 1:0.5 3:2\n"[..], &options)?;
//! let digest = canonical_sha256(&components)?;
//! assert_eq!(digest.len(), 32);
//! # Ok::<(), datamonger_core::Error>(())
//! ```

mod canonical;
mod compression;
mod decode;
mod error;
mod model;

pub use canonical::{
    canonical_sha256, canonical_sha256_with_control, write_canonical, write_canonical_with_control,
    EMIT_BYTES,
};
pub use compression::{
    artifact_reader, artifact_reader_with_options, decode_gzip_single_member,
    ArtifactReaderOptions, Compression,
};
pub use decode::{
    decode_delimited, decode_delimited_with_control, decode_delimited_with_options, decode_libsvm,
    decode_libsvm_split, decode_libsvm_split_version_with_control,
    decode_libsvm_split_version_with_options, decode_libsvm_split_with_control,
    decode_libsvm_split_with_options, decode_libsvm_version_with_control,
    decode_libsvm_version_with_options, decode_libsvm_with_control, decode_libsvm_with_options,
    parse_binary64, Column, DecodeOptions, DelimitedOptions, LabelType, LibsvmOptions,
};
pub use error::{Error, ErrorKind, Result};
pub use model::{Component, DataType, Shape, Values};

/// A caller-supplied cancellation checkpoint. Implementations must return errors
/// normally rather than unwind or jump across runtime boundaries.
pub trait Control {
    /// Check whether decoding or serialization should continue.
    fn checkpoint(&mut self) -> Result<()>;
}

impl<F: FnMut() -> Result<()>> Control for F {
    fn checkpoint(&mut self) -> Result<()> {
        self()
    }
}
