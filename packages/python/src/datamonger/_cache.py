"""Verified, single-process content-addressed cache publication."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import urllib.error
import urllib.request
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
            content_encoding = response.headers.get("Content-Encoding")
            normalized_encoding = (
                content_encoding.strip().lower()
                if content_encoding is not None
                else None
            )
            if normalized_encoding not in {None, "identity"}:
                raise retrieval_error(
                    f"unsupported HTTP content coding {content_encoding!r} from {url}"
                )
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, prefix=".download-", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                actual = hashlib.sha256()
                count = 0
                while chunk := response.read(_CHUNK_SIZE):
                    temporary.write(chunk)
                    actual.update(chunk)
                    count += len(chunk)
                    if size is not None and count > size:
                        raise integrity_error(
                            f"size mismatch for {url}: expected {size}, "
                            f"received more than {size}"
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
        os.replace(temporary_path, target)
        temporary_path = None
        return target
    except DatamongerError:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise retrieval_error(f"cannot retrieve {url}: {error}") from error
    finally:
        if temporary_path is not None:
            with suppress(OSError):
                temporary_path.unlink(missing_ok=True)
