use std::io::{BufReader, Read, Write};
use std::time::Duration;

use flate2::bufread::GzDecoder;
use reqwest::blocking::{Client, Response};
use reqwest::header::{ACCEPT_ENCODING, CONTENT_ENCODING};
use reqwest::redirect::Policy;

use crate::error::{Error, Result};

pub struct HttpClient(Client);

impl HttpClient {
    pub fn new() -> Result<Self> {
        let policy = Policy::custom(|attempt| {
            if attempt.previous().len() >= 10 {
                attempt.error("too many redirects")
            } else if !matches!(attempt.url().scheme(), "http" | "https") {
                attempt.error("redirect target must be HTTP(S)")
            } else {
                attempt.follow()
            }
        });
        let client = Client::builder()
            .tls_backend_rustls()
            .no_gzip()
            .no_brotli()
            .no_deflate()
            .no_zstd()
            .redirect(policy)
            .timeout(Duration::from_secs(60))
            .build()
            .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?;
        Ok(Self(client))
    }

    fn response(&self, url: &str, https_only: bool) -> Result<Response> {
        let parsed = reqwest::Url::parse(url)
            .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?;
        if !matches!(parsed.scheme(), "http" | "https")
            || parsed.host_str().is_none()
            || (https_only && parsed.scheme() != "https")
        {
            return Err(Error::new("retrieval-exhausted", "invalid HTTP(S) URL"));
        }
        let response = self
            .0
            .get(parsed)
            .header(ACCEPT_ENCODING, "identity")
            .send()
            .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?;
        if https_only && response.url().scheme() != "https" {
            return Err(Error::new(
                "retrieval-exhausted",
                "catalog redirected to a non-HTTPS URL",
            ));
        }
        if !response.status().is_success() {
            return Err(Error::new(
                "retrieval-exhausted",
                format!("{} returned HTTP {}", response.url(), response.status()),
            ));
        }
        Ok(response)
    }

    pub fn download<W: Write>(&self, url: &str, https_only: bool, output: &mut W) -> Result<()> {
        let response = self.response(url, https_only)?;
        let codings: Vec<_> = response
            .headers()
            .get_all(CONTENT_ENCODING)
            .iter()
            .collect();
        if codings.len() > 1 {
            return Err(Error::new(
                "retrieval-exhausted",
                "multiply declared Content-Encoding",
            ));
        }
        let coding = match codings.first() {
            None => "identity",
            Some(value) => value
                .to_str()
                .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?
                .trim(),
        };
        match coding.to_ascii_lowercase().as_str() {
            "identity" => copy(response, output),
            "gzip" | "x-gzip" => {
                let mut decoder = GzDecoder::new(BufReader::new(response));
                copy(&mut decoder, output)?;
                let mut rest = decoder.into_inner();
                let mut trailing = [0_u8; 1];
                if rest
                    .read(&mut trailing)
                    .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?
                    != 0
                {
                    return Err(Error::new(
                        "retrieval-exhausted",
                        "concatenated or trailing gzip content coding bytes",
                    ));
                }
                Ok(())
            }
            _ => Err(Error::new(
                "retrieval-exhausted",
                format!("unsupported Content-Encoding {coding:?}"),
            )),
        }
    }

    pub fn get_bytes(&self, url: &str, https_only: bool) -> Result<Vec<u8>> {
        let mut bytes = Vec::new();
        self.download(url, https_only, &mut bytes)?;
        Ok(bytes)
    }
}

fn copy<R: Read, W: Write>(mut input: R, output: &mut W) -> Result<()> {
    std::io::copy(&mut input, output)
        .map_err(|error| Error::new("retrieval-exhausted", error.to_string()))?;
    Ok(())
}
