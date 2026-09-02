"""Public inspection and manual eviction for the private Python cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from datamonger._cache import _cleaner_lease, _reader_lease, default_cache_root
from datamonger._errors import CacheError
from datamonger._models import (
    CacheCleanResult,
    CacheEntry,
    CacheEntryKind,
    CacheInfo,
    Pathish,
)
from datamonger._registry import bundled_registry_bytes

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DATASET_ID = re.compile(
    r"[a-z0-9][a-z0-9._-]*:[a-z0-9][a-z0-9._-]*@"
    r"[A-Za-z0-9][A-Za-z0-9._+-]*\Z"
)
_CACHE_KINDS: tuple[tuple[str, CacheEntryKind], ...] = (
    ("objects", "artifact"),
    ("registries", "registry"),
)


def _cache_paths(cache_root: Path, namespace: str) -> tuple[Path, ...]:
    directory = cache_root / namespace / "sha256"
    try:
        return tuple(
            sorted(
                (
                    path
                    for path in directory.iterdir()
                    if _SHA256.fullmatch(path.name) is not None
                    and path.is_file()
                    and not path.is_symlink()
                ),
                key=lambda path: path.name,
            )
        )
    except FileNotFoundError:
        return ()
    except OSError as error:
        raise CacheError(
            f"cannot inspect cache directory {directory}: {error}"
        ) from error


def _inspect_entry(
    cache_root: Path,
    namespace: str,
    kind: CacheEntryKind,
    path: Path,
    *,
    acquire_lease: bool = True,
) -> tuple[CacheEntry, bytes | None] | None:
    digest = path.name
    try:
        lease = (
            _reader_lease(cache_root, namespace, digest)
            if acquire_lease
            else nullcontext()
        )
        with lease, path.open("rb") as source:
            if kind == "registry":
                contents = source.read()
                actual_digest = hashlib.sha256(contents).hexdigest()
            else:
                contents = None
                actual_digest = hashlib.file_digest(source, "sha256").hexdigest()
            stat = os.fstat(source.fileno())
    except FileNotFoundError:
        return None
    except OSError as error:
        raise CacheError(f"cannot inspect cached object {path}: {error}") from error

    return (
        CacheEntry(
            kind=kind,
            sha256=digest,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            path=path,
            valid=actual_digest == digest,
            datasets=(),
            registry_release=None,
        ),
        contents,
    )


def _registry_metadata(contents: bytes) -> tuple[str | None, dict[str, set[str]]]:
    try:
        value = json.loads(contents)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, {}
    if not isinstance(value, Mapping) or value.get("schema_version") != 1:
        return None, {}

    release = value.get("release")
    registry_release = release if isinstance(release, str) else None
    references: dict[str, set[str]] = {}
    datasets = value.get("datasets")
    if not isinstance(datasets, list):
        return registry_release, references
    for raw_dataset in datasets:
        if not isinstance(raw_dataset, Mapping):
            continue
        source = raw_dataset.get("source")
        name = raw_dataset.get("name")
        version = raw_dataset.get("version")
        artifacts = raw_dataset.get("artifacts")
        if not all(isinstance(part, str) for part in (source, name, version)):
            continue
        if not isinstance(artifacts, list):
            continue
        dataset_id = f"{source}:{name}@{version}"
        for raw_artifact in artifacts:
            if not isinstance(raw_artifact, Mapping):
                continue
            digest = raw_artifact.get("sha256")
            if isinstance(digest, str) and _SHA256.fullmatch(digest) is not None:
                references.setdefault(digest, set()).add(dataset_id)
    return registry_release, references


def _merge_references(
    target: dict[str, set[str]], source: Mapping[str, set[str]]
) -> None:
    for digest, datasets in source.items():
        target.setdefault(digest, set()).update(datasets)


def cache_info(*, cache_dir: Pathish | None = None) -> CacheInfo:
    """Report cached registries and artifacts without accessing the network."""

    cache_root = Path(cache_dir) if cache_dir is not None else default_cache_root()
    entries: list[CacheEntry] = []
    references: dict[str, set[str]] = {}

    _, bundled_references = _registry_metadata(bundled_registry_bytes())
    _merge_references(references, bundled_references)

    for namespace, kind in _CACHE_KINDS:
        for path in _cache_paths(cache_root, namespace):
            inspected = _inspect_entry(cache_root, namespace, kind, path)
            if inspected is None:
                continue
            entry, contents = inspected
            if kind == "registry" and entry.valid and contents is not None:
                release, registry_references = _registry_metadata(contents)
                entry = replace(entry, registry_release=release)
                _merge_references(references, registry_references)
            entries.append(entry)

    entries = [
        replace(entry, datasets=tuple(sorted(references.get(entry.sha256, ()))))
        if entry.kind == "artifact"
        else entry
        for entry in entries
    ]
    entries.sort(key=lambda entry: (entry.kind, entry.sha256))
    return CacheInfo(
        location=cache_root,
        total_size=sum(entry.size for entry in entries),
        entries=tuple(entries),
    )


def _selected(
    entry: CacheEntry,
    *,
    dataset: str | None,
    cutoff: datetime | None,
) -> bool:
    matches_dataset = dataset is None or (
        entry.kind == "artifact" and dataset in entry.datasets
    )
    matches_age = cutoff is None or entry.modified_at <= cutoff
    return matches_dataset and matches_age


def cache_clean(
    *,
    dataset: str | None = None,
    older_than: timedelta | None = None,
    cache_dir: Pathish | None = None,
) -> CacheCleanResult:
    """Manually evict matching entries, skipping any object with an active lease.

    With no filters, all registry and artifact entries are selected. ``dataset``
    is a canonical identifier such as ``"uci:iris@1"``. When both filters are
    supplied, only entries matching both are selected.
    """

    if dataset is not None and (
        not isinstance(dataset, str) or _DATASET_ID.fullmatch(dataset) is None
    ):
        raise ValueError("dataset must be a canonical source:name@version identifier")
    if older_than is not None and older_than < timedelta(0):
        raise ValueError("older_than must be nonnegative")

    info = cache_info(cache_dir=cache_dir)
    cutoff = datetime.now(UTC) - older_than if older_than is not None else None
    removed: list[CacheEntry] = []
    skipped: list[CacheEntry] = []
    namespace_for_kind = {kind: namespace for namespace, kind in _CACHE_KINDS}

    for entry in info.entries:
        if not _selected(entry, dataset=dataset, cutoff=cutoff):
            continue
        namespace = namespace_for_kind[entry.kind]
        with _cleaner_lease(info.location, namespace, entry.sha256) as acquired:
            if not acquired:
                skipped.append(entry)
                continue
            inspected = _inspect_entry(
                info.location,
                namespace,
                entry.kind,
                entry.path,
                acquire_lease=False,
            )
            if inspected is None:
                continue
            current, contents = inspected
            current = replace(current, datasets=entry.datasets)
            if current.kind == "registry" and current.valid and contents is not None:
                release, _ = _registry_metadata(contents)
                current = replace(current, registry_release=release)
            if not _selected(current, dataset=dataset, cutoff=cutoff):
                continue
            try:
                current.path.unlink()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise CacheError(
                    f"cannot remove cached object {current.path}: {error}"
                ) from error
            removed.append(current)

    return CacheCleanResult(
        location=info.location,
        removed=tuple(removed),
        skipped=tuple(skipped),
    )
