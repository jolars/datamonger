use std::io::{BufRead, BufReader, Read, Write};

use crate::{Error, ErrorKind, Result};

/// Manifest-declared artifact compression.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Compression {
    /// Uncompressed bytes.
    None,
    /// Gzip compression.
    Gzip,
    /// Bzip2 compression.
    Bzip2,
}

/// Wrap an artifact reader without materializing its decompressed contents.
/// HTTP content coding must be removed and verified before using this reader.
pub fn artifact_reader<'a, R: Read + 'a>(
    reader: R,
    compression: Compression,
) -> Box<dyn BufRead + 'a> {
    match compression {
        Compression::None => Box::new(BufReader::new(reader)),
        Compression::Gzip => Box::new(BufReader::new(flate2::read::MultiGzDecoder::new(reader))),
        Compression::Bzip2 => Box::new(BufReader::new(bzip2::read::MultiBzDecoder::new(reader))),
    }
}

/// Decode exactly one HTTP gzip member, validating its trailer and rejecting
/// additional members or trailing bytes. The buffered reader prevents read-ahead
/// from hiding bytes after the member.
pub fn decode_gzip_single_member<R: BufRead, W: Write>(reader: R, mut writer: W) -> Result<()> {
    let mut decoder = flate2::bufread::GzDecoder::new(reader);
    std::io::copy(&mut decoder, &mut writer).map_err(|e| {
        Error::new(
            ErrorKind::Decode,
            format!("malformed or truncated gzip stream: {e}"),
        )
    })?;
    if !decoder.into_inner().fill_buf()?.is_empty() {
        return Err(Error::new(
            ErrorKind::Decode,
            "gzip stream contains trailing bytes or additional members",
        ));
    }
    Ok(())
}
