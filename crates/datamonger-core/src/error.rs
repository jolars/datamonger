use std::fmt;

/// Portable error categories for language bindings.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ErrorKind {
    /// An unsupported or inconsistent representation recipe.
    UnsupportedDecoder,
    /// Invalid artifact text or compression.
    Decode,
    /// Invalid canonical logical components.
    DecodedIntegrity,
    /// A reader or writer failed.
    Io,
    /// The caller canceled the operation.
    Interrupted,
}

/// A diagnostic with a stable category and a human-readable explanation.
#[derive(Debug)]
pub struct Error {
    /// The category, independent of a host runtime's exception classes.
    pub kind: ErrorKind,
    message: String,
    source: Option<std::io::Error>,
}

impl Error {
    /// Construct an error without a lower-level I/O cause.
    pub fn new(kind: ErrorKind, message: impl Into<String>) -> Self {
        Self {
            kind,
            message: message.into(),
            source: None,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        self.source.as_ref().map(|e| e as _)
    }
}

impl From<std::io::Error> for Error {
    fn from(source: std::io::Error) -> Self {
        Self {
            kind: ErrorKind::Io,
            message: source.to_string(),
            source: Some(source),
        }
    }
}

/// The result type used by the core.
pub type Result<T> = std::result::Result<T, Error>;
