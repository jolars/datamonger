"""Verified, single-process content-addressed cache publication."""

from __future__ import annotations

import hashlib
import http.client
import os
import re
import tempfile
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

from platformdirs import user_cache_path

from datamonger._errors import CacheError, DatamongerError, RetrievalError

_CHUNK_SIZE = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_NAMESPACES = {"objects", "registries"}


def default_cache_root() -> Path:
    """Return the Python client's private application cache root."""

    return user_cache_path("datamonger") / "python"


def _matches(path: Path, digest: str, size: int | None) -> bool:
    actual = hashlib.sha256()
    count = 0
    try:
        with path.open("rb") as source:
            while chunk := source.read(_CHUNK_SIZE):
                actual.update(chunk)
                count += len(chunk)
    except OSError as error:
        raise CacheError(f"cannot read cached object {path}: {error}") from error
    return actual.hexdigest() == digest and (size is None or count == size)


def _content_decoder(
    header: str | None,
    url: str,
    retrieval_error: Callable[[str], DatamongerError],
) -> zlib._Decompress | None:
    """Return a decompressor for the declared content codings, if any."""

    if header is None:
        return None
    codings = [coding.strip().lower() for coding in header.split(",")]
    codings = [coding for coding in codings if coding not in {"", "identity"}]
    if not codings:
        return None
    # The artifact is defined as the content after the declared codings are
    # removed. We undo gzip because CDNs apply it despite Accept-Encoding:
    # identity; anything else stays unsupported rather than guessed at.
    if codings in (["gzip"], ["x-gzip"]):
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    raise retrieval_error(f"unsupported HTTP content coding {header!r} from {url}")


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise CacheError(
            f"cannot discard invalid cache object {path}: {error}"
        ) from error


def verified_download(
    *,
    cache_root: Path,
    namespace: str,
    url: str,
    digest: str,
    size: int | None,
    integrity_error: Callable[[str], DatamongerError],
    retrieval_error: Callable[[str], DatamongerError] = RetrievalError,
) -> Path:
    """Return a verified cached URL response, downloading it when absent."""

    if namespace not in _NAMESPACES:
        raise CacheError(f"unsupported cache namespace {namespace!r}")
    if _SHA256.fullmatch(digest) is None:
        raise integrity_error(f"invalid expected SHA-256 digest {digest!r}")
    if size is not None and size < 0:
        raise integrity_error(f"invalid expected size {size}")
    if urlsplit(url).scheme not in {"http", "https"}:
        raise retrieval_error(f"unsupported retrieval URL scheme for {url!r}")

    target = cache_root / namespace / "sha256" / digest
    if target.exists():
        if _matches(target, digest, size):
            return target
        _unlink(target)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise CacheError(
            f"cannot create cache directory {target.parent}: {error}"
        ) from error

    temporary_path: Path | None = None
    try:
        request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=30) as response:
            decoder = _content_decoder(
                response.headers.get("Content-Encoding"), url, retrieval_error
            )
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".download-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                actual = hashlib.sha256()
                count = 0

                # Hash and size-check the decoded stream: the artifact is the
                # content after HTTP content codings are removed.
                def emit(data: bytes) -> None:
                    nonlocal count
                    temporary.write(data)
                    actual.update(data)
                    count += len(data)
                    if size is not None and count > size:
                        raise integrity_error(
                            f"size mismatch for {url}: expected {size}, "
                            f"received more than {size}"
                        )

                while chunk := response.read(_CHUNK_SIZE):
                    emit(decoder.decompress(chunk) if decoder else chunk)
                if decoder is not None:
                    emit(decoder.flush())
                    if not decoder.eof:
                        raise retrieval_error(f"truncated gzip content from {url}")
                temporary.flush()
                os.fsync(temporary.fileno())

        if size is not None and count != size:
            raise integrity_error(
                f"size mismatch for {url}: expected {size}, received {count}"
            )
        actual_digest = actual.hexdigest()
        if actual_digest != digest:
            message = (
                f"SHA-256 mismatch for {url}: expected {digest}, "
                f"received {actual_digest}"
            )
            raise integrity_error(message)
        os.replace(temporary_path, target)
        temporary_path = None
        return target
    except DatamongerError:
        raise
    except (
        OSError,
        urllib.error.URLError,
        http.client.HTTPException,
        zlib.error,
    ) as error:
        raise retrieval_error(f"cannot retrieve {url}: {error}") from error
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
