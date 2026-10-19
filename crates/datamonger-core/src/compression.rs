use std::io::{self, BufRead, BufReader, Read, Write};

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
    artifact_reader_with_options(reader, compression, ArtifactReaderOptions::default())
}

/// Compatibility choices for existing clients' artifact decompression.
/// These do not apply to HTTP content coding.
#[derive(Clone, Copy, Debug, Default)]
pub struct ArtifactReaderOptions {
    /// Permit zero bytes between and after gzip members, as Python's gzip reader does.
    pub gzip_zero_padding: bool,
    /// Ignore an invalid new bzip2 member after a complete member, as Python's
    /// bzip2 reader does. An incomplete member still fails at EOF.
    pub bzip2_trailing_data: bool,
}

/// Wrap an artifact reader with explicit compressed-stream compatibility.
/// The default options retain the strict behavior of [`artifact_reader`].
pub fn artifact_reader_with_options<'a, R: Read + 'a>(
    reader: R,
    compression: Compression,
    options: ArtifactReaderOptions,
) -> Box<dyn BufRead + 'a> {
    match compression {
        Compression::None => Box::new(BufReader::new(reader)),
        Compression::Gzip if options.gzip_zero_padding => Box::new(BufReader::new(GzipMembers {
            reader: Some(BufReader::new(reader)),
            decoder: None,
            first: true,
        })),
        Compression::Bzip2 if options.bzip2_trailing_data => {
            Box::new(BufReader::new(Bzip2Members {
                reader: BufReader::new(reader),
                decoder: bzip2::Decompress::new(false),
                member_end: false,
                eof: false,
            }))
        }
        Compression::Gzip => Box::new(BufReader::new(flate2::read::MultiGzDecoder::new(reader))),
        Compression::Bzip2 => Box::new(BufReader::new(bzip2::read::MultiBzDecoder::new(reader))),
    }
}

struct GzipMembers<R: Read> {
    reader: Option<BufReader<R>>,
    decoder: Option<flate2::bufread::GzDecoder<BufReader<R>>>,
    first: bool,
}

impl<R: Read> Read for GzipMembers<R> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        if output.is_empty() {
            return Ok(0);
        }
        loop {
            if let Some(decoder) = &mut self.decoder {
                let count = decoder.read(output)?;
                if count > 0 {
                    return Ok(count);
                }
                self.reader = self.decoder.take().map(|decoder| decoder.into_inner());
                self.first = false;
            }
            let Some(mut reader) = self.reader.take() else {
                return Ok(0);
            };
            if !self.first {
                loop {
                    let bytes = reader.fill_buf()?;
                    let padding = bytes.iter().take_while(|&&b| b == 0).count();
                    if padding == 0 {
                        break;
                    }
                    reader.consume(padding);
                }
            }
            if reader.fill_buf()?.is_empty() {
                return Ok(0);
            }
            self.decoder = Some(flate2::bufread::GzDecoder::new(reader));
        }
    }
}

struct Bzip2Members<R> {
    reader: R,
    decoder: bzip2::Decompress,
    member_end: bool,
    eof: bool,
}

impl<R: BufRead> Read for Bzip2Members<R> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        if self.eof || output.is_empty() {
            return Ok(0);
        }
        loop {
            let input = self.reader.fill_buf()?;
            let trailing = self.member_end;
            if trailing {
                if input.is_empty() {
                    self.eof = true;
                    return Ok(0);
                }
                self.decoder = bzip2::Decompress::new(false);
                self.member_end = false;
            }
            let before_in = self.decoder.total_in();
            let before_out = self.decoder.total_out();
            let status = self.decoder.decompress(input, output);
            let consumed = (self.decoder.total_in() - before_in) as usize;
            let count = (self.decoder.total_out() - before_out) as usize;
            let remaining = input.len() - consumed;
            self.reader.consume(consumed);
            match status {
                // Only the first decompression attempt after a complete member
                // may identify ignored trailing data. Later corruption fails.
                Err(_) if trailing => {
                    self.eof = true;
                    return Ok(0);
                }
                Err(error) => return Err(io::Error::new(io::ErrorKind::InvalidData, error)),
                Ok(bzip2::Status::StreamEnd) => self.member_end = true,
                Ok(_) if consumed == 0 && remaining == 0 && count == 0 => {
                    return Err(io::Error::new(
                        io::ErrorKind::UnexpectedEof,
                        "incomplete bzip2 member",
                    ));
                }
                Ok(_) => {}
            }
            if count > 0 {
                return Ok(count);
            }
        }
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

#[cfg(test)]
mod tests {
    use super::*;

    fn compressed(compression: Compression, bytes: &[u8]) -> Vec<u8> {
        match compression {
            Compression::Gzip => {
                let mut encoder = flate2::write::GzEncoder::new(Vec::new(), Default::default());
                encoder.write_all(bytes).unwrap();
                encoder.finish().unwrap()
            }
            Compression::Bzip2 => {
                let mut encoder = bzip2::write::BzEncoder::new(Vec::new(), Default::default());
                encoder.write_all(bytes).unwrap();
                encoder.finish().unwrap()
            }
            Compression::None => bytes.to_vec(),
        }
    }

    const COMPATIBLE: ArtifactReaderOptions = ArtifactReaderOptions {
        gzip_zero_padding: true,
        bzip2_trailing_data: true,
    };

    #[test]
    fn trailing_data_requires_explicit_compatibility() {
        for (compression, suffix) in [
            (Compression::Gzip, b"\0".as_slice()),
            (Compression::Bzip2, b"junk".as_slice()),
        ] {
            let mut bytes = compressed(compression, b"first\n");
            bytes.extend_from_slice(suffix);
            let mut output = Vec::new();
            assert!(artifact_reader(bytes.as_slice(), compression)
                .read_to_end(&mut output)
                .is_err());
            output.clear();
            artifact_reader_with_options(bytes.as_slice(), compression, COMPATIBLE)
                .read_to_end(&mut output)
                .unwrap();
            assert_eq!(output, b"first\n");
        }
    }

    #[test]
    fn compatible_readers_validate_members_and_concatenate_them() {
        for compression in [Compression::Gzip, Compression::Bzip2] {
            let mut bytes = compressed(compression, b"first\n");
            if compression == Compression::Gzip {
                bytes.extend_from_slice(&[0; 8193]);
            }
            bytes.extend_from_slice(&compressed(compression, b"second\n"));
            let mut output = Vec::new();
            artifact_reader_with_options(bytes.as_slice(), compression, COMPATIBLE)
                .read_to_end(&mut output)
                .unwrap();
            assert_eq!(output, b"first\nsecond\n");
            bytes.pop();
            assert!(
                artifact_reader_with_options(bytes.as_slice(), compression, COMPATIBLE)
                    .read_to_end(&mut Vec::new())
                    .is_err()
            );
        }
    }
}
