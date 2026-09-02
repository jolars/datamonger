"""Verified content-addressed cache publication and object leases."""

from __future__ import annotations

import hashlib
import http.client
import os
import re
import tempfile
import urllib.error
import urllib.request
import zlib
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit

import portalocker
from platformdirs import user_cache_path

from datamonger._errors import CacheError, DatamongerError, RetrievalError

_CHUNK_SIZE = 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_HTTP_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
_NAMESPACES = {"objects", "registries"}


def default_cache_root() -> Path:
    """Return the Python client's private application cache root."""

    return user_cache_path("datamonger") / "python"


def _lease_path(
    cache_root: Path, namespace: str, digest: str, *, publication: bool = False
) -> Path:
    if namespace not in _NAMESPACES:
        raise CacheError(f"unsupported cache namespace {namespace!r}")
    if _SHA256.fullmatch(digest) is None:
        raise CacheError(f"invalid cache lease SHA-256 digest {digest!r}")
    suffix = ".publish.lock" if publication else ".lock"
    return cache_root / ".leases" / namespace / "sha256" / f"{digest}{suffix}"


@contextmanager
def _lease(path: Path, *, exclusive: bool, blocking: bool) -> Iterator[bool]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lease_file: BinaryIO = path.open("a+b")
    except OSError as error:
        raise CacheError(f"cannot open cache lease {path}: {error}") from error

    flags = (
        portalocker.LockFlags.EXCLUSIVE if exclusive else portalocker.LockFlags.SHARED
    )
    if not blocking:
        flags |= portalocker.LockFlags.NON_BLOCKING
    acquired = False
    try:
        try:
            portalocker.lock(lease_file, flags)
            acquired = True
        except portalocker.AlreadyLocked:
            if blocking:
                raise CacheError(f"cannot acquire cache lease {path}") from None
        except (OSError, portalocker.LockException) as error:
            raise CacheError(f"cannot acquire cache lease {path}: {error}") from error
        yield acquired
    finally:
        try:
            if acquired:
                portalocker.unlock(lease_file)
        except (OSError, portalocker.LockException) as error:
            raise CacheError(f"cannot release cache lease {path}: {error}") from error
        finally:
            lease_file.close()


@contextmanager
def _publisher_lease(cache_root: Path, namespace: str, digest: str) -> Iterator[None]:
    """Hold the shared side of an object's lease while publishing it."""

    with _lease(
        _lease_path(cache_root, namespace, digest),
        exclusive=False,
        blocking=True,
    ) as acquired:
        if not acquired:  # pragma: no cover - blocking acquisition cannot skip.
            raise CacheError("cache publisher lease was unexpectedly skipped")
        yield


@contextmanager
def _reader_lease(cache_root: Path, namespace: str, digest: str) -> Iterator[None]:
    """Hold the shared side of an object's lease while reading it."""

    with _lease(
        _lease_path(cache_root, namespace, digest),
        exclusive=False,
        blocking=True,
    ) as acquired:
        if not acquired:  # pragma: no cover - blocking acquisition cannot skip.
            raise CacheError("cache reader lease was unexpectedly skipped")
        yield


@contextmanager
def _cleaner_lease(cache_root: Path, namespace: str, digest: str) -> Iterator[bool]:
    """Try to hold the exclusive side of an object's lease without waiting."""

    with _lease(
        _lease_path(cache_root, namespace, digest),
        exclusive=True,
        blocking=False,
    ) as acquired:
        yield acquired


@contextmanager
def _publication_lock(cache_root: Path, namespace: str, digest: str) -> Iterator[None]:
    """Serialize the short validation and atomic-commit phases."""

    with _lease(
        _lease_path(cache_root, namespace, digest, publication=True),
        exclusive=True,
        blocking=True,
    ) as acquired:
        if not acquired:  # pragma: no cover - blocking acquisition cannot skip.
            raise CacheError("cache publication lock was unexpectedly skipped")
        yield


def _matches(path: Path, digest: str, size: int | None) -> bool:
    try:
        with path.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256")
            count = source.tell()
    except OSError as error:
        raise CacheError(f"cannot read cached object {path}: {error}") from error
    return actual.hexdigest() == digest and (size is None or count == size)


def _content_decoder(
    headers: Sequence[str],
    url: str,
    retrieval_error: Callable[[str], DatamongerError],
) -> zlib._Decompress | None:
    """Return a decompressor for the declared content codings, if any."""

    if not headers:
        return None
    header = ", ".join(headers)
    codings = [coding.strip() for value in headers for coding in value.split(",")]
    if any(_HTTP_TOKEN.fullmatch(coding) is None for coding in codings):
        raise retrieval_error(f"malformed HTTP content coding {header!r} from {url}")
    non_identity = [
        coding.lower() for coding in codings if coding.lower() != "identity"
    ]
    if len(non_identity) > 1:
        raise retrieval_error(f"multiple HTTP content codings {header!r} from {url}")
    if not non_identity:
        return None
    # The artifact is defined as the content after the declared codings are
    # removed. We undo gzip because CDNs apply it despite Accept-Encoding:
    # identity; anything else stays unsupported rather than guessed at.
    if non_identity[0] in {"gzip", "x-gzip"}:
        return zlib.decompressobj(16 + zlib.MAX_WBITS)
    raise retrieval_error(f"unsupported HTTP content coding {header!r} from {url}")


def _content_length(
    headers: Sequence[str],
    url: str,
    retrieval_error: Callable[[str], DatamongerError],
) -> int | None:
    """Validate and return the response's encoded content length."""

    if not headers:
        return None
    values = [value.strip() for header in headers for value in header.split(",")]
    if any(not value.isascii() or not value.isdecimal() for value in values):
        raise retrieval_error(f"malformed HTTP Content-Length from {url}")
    lengths = {int(value) for value in values}
    if len(lengths) != 1:
        raise retrieval_error(f"conflicting HTTP Content-Length values from {url}")
    return lengths.pop()


def _has_transfer_coding(
    headers: Sequence[str],
    url: str,
    retrieval_error: Callable[[str], DatamongerError],
) -> bool:
    """Validate transfer coding handled by the HTTP stack."""

    if not headers:
        return False
    codings = [
        coding.strip().lower() for value in headers for coding in value.split(",")
    ]
    if codings != ["chunked"]:
        header = ", ".join(headers)
        raise retrieval_error(f"unsupported HTTP transfer coding {header!r} from {url}")
    return True


def _unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise CacheError(
            f"cannot discard invalid cache object {path}: {error}"
        ) from error


def _validate_download(
    *,
    cache_root: Path,
    namespace: str,
    url: str,
    digest: str,
    size: int | None,
    integrity_error: Callable[[str], DatamongerError],
    retrieval_error: Callable[[str], DatamongerError] = RetrievalError,
) -> Path:
    if namespace not in _NAMESPACES:
        raise CacheError(f"unsupported cache namespace {namespace!r}")
    if _SHA256.fullmatch(digest) is None:
        raise integrity_error(f"invalid expected SHA-256 digest {digest!r}")
    if size is not None and size < 0:
        raise integrity_error(f"invalid expected size {size}")
    if urlsplit(url).scheme not in {"http", "https"}:
        raise retrieval_error(f"unsupported retrieval URL scheme for {url!r}")
    return cache_root / namespace / "sha256" / digest


def _ensure_cached(
    *,
    cache_root: Path,
    namespace: str,
    target: Path,
    url: str,
    digest: str,
    size: int | None,
    integrity_error: Callable[[str], DatamongerError],
    retrieval_error: Callable[[str], DatamongerError],
) -> Path:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise CacheError(
            f"cannot create cache directory {target.parent}: {error}"
        ) from error

    # Publishers may download concurrently, but serializing the short check and
    # commit phases avoids replacing a complete object that another publisher
    # has just made available.
    with _publication_lock(cache_root, namespace, digest):
        if target.exists():
            if _matches(target, digest, size):
                return target
            _unlink(target)

    temporary_path: Path | None = None
    try:
        request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(request, timeout=30) as response:
            decoder = _content_decoder(
                response.headers.get_all("Content-Encoding", []), url, retrieval_error
            )
            has_transfer_coding = _has_transfer_coding(
                response.headers.get_all("Transfer-Encoding", []),
                url,
                retrieval_error,
            )
            encoded_size = None
            if not has_transfer_coding:
                encoded_size = _content_length(
                    response.headers.get_all("Content-Length", []),
                    url,
                    retrieval_error,
                )
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".download-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                actual = hashlib.sha256()
                count = 0
                encoded_count = 0

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
                    encoded_count += len(chunk)
                    if decoder is None:
                        emit(chunk)
                        continue
                    compressed = chunk
                    while compressed:
                        emit(decoder.decompress(compressed, _CHUNK_SIZE))
                        if decoder.unused_data:
                            raise retrieval_error(f"data after gzip stream from {url}")
                        compressed = decoder.unconsumed_tail
                if decoder is not None:
                    emit(decoder.flush())
                    if not decoder.eof:
                        raise retrieval_error(f"truncated gzip content from {url}")
                    if decoder.unused_data:
                        raise retrieval_error(f"data after gzip stream from {url}")
                if encoded_size is not None and encoded_count != encoded_size:
                    raise retrieval_error(
                        f"truncated HTTP content from {url}: expected "
                        f"{encoded_size} bytes, received {encoded_count}"
                    )
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

        with _publication_lock(cache_root, namespace, digest):
            if target.exists() and _matches(target, digest, size):
                _unlink(temporary_path)
                temporary_path = None
            else:
                if target.exists():
                    _unlink(target)
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


@contextmanager
def verified_download_lease(
    *,
    cache_root: Path,
    namespace: str,
    url: str,
    digest: str,
    size: int | None,
    integrity_error: Callable[[str], DatamongerError],
    retrieval_error: Callable[[str], DatamongerError] = RetrievalError,
) -> Iterator[Path]:
    """Yield a verified path while retaining its reader lease."""

    target = _validate_download(
        cache_root=cache_root,
        namespace=namespace,
        url=url,
        digest=digest,
        size=size,
        integrity_error=integrity_error,
        retrieval_error=retrieval_error,
    )
    with _publisher_lease(cache_root, namespace, digest):
        path = _ensure_cached(
            cache_root=cache_root,
            namespace=namespace,
            target=target,
            url=url,
            digest=digest,
            size=size,
            integrity_error=integrity_error,
            retrieval_error=retrieval_error,
        )
        with _reader_lease(cache_root, namespace, digest):
            yield path


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

    with verified_download_lease(
        cache_root=cache_root,
        namespace=namespace,
        url=url,
        digest=digest,
        size=size,
        integrity_error=integrity_error,
        retrieval_error=retrieval_error,
    ) as path:
        return path
