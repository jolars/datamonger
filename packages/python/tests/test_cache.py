from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from datamonger import cache_clean, cache_info
from datamonger._cache import _cleaner_lease, _publisher_lease, _reader_lease

_DIGEST = "a" * 64


def _write_cache_fixture(cache_root: Path) -> tuple[str, str, str]:
    shared = b"shared artifact"
    other = b"other artifact"
    shared_digest = hashlib.sha256(shared).hexdigest()
    other_digest = hashlib.sha256(other).hexdigest()
    datasets = [
        {
            "schema_version": 1,
            "source": "fixture",
            "name": "first",
            "version": "1",
            "artifacts": [
                {"name": "data", "sha256": shared_digest, "size": len(shared)}
            ],
        },
        {
            "schema_version": 1,
            "source": "fixture",
            "name": "second",
            "version": "2",
            "artifacts": [
                {"name": "train", "sha256": shared_digest, "size": len(shared)},
                {"name": "test", "sha256": other_digest, "size": len(other)},
            ],
        },
    ]
    index = {
        "schema_version": 1,
        "release": "cache-test-1",
        "defaults": [],
        "datasets": datasets,
    }
    index_bytes = json.dumps(index, separators=(",", ":")).encode()
    index_digest = hashlib.sha256(index_bytes).hexdigest()
    registry_dir = cache_root / "registries" / "sha256"
    object_dir = cache_root / "objects" / "sha256"
    registry_dir.mkdir(parents=True)
    object_dir.mkdir(parents=True)
    (registry_dir / index_digest).write_bytes(index_bytes)
    (object_dir / shared_digest).write_bytes(shared)
    (object_dir / other_digest).write_bytes(other)
    return index_digest, shared_digest, other_digest


def test_cache_info_reports_size_validity_and_dataset_references(
    tmp_path: Path,
) -> None:
    index_digest, shared_digest, other_digest = _write_cache_fixture(tmp_path)

    info = cache_info(cache_dir=tmp_path)

    assert info.location == tmp_path
    assert info.total_size == sum(entry.size for entry in info.entries)
    assert {entry.sha256 for entry in info.entries} == {
        index_digest,
        shared_digest,
        other_digest,
    }
    assert all(entry.valid for entry in info.entries)
    shared = next(entry for entry in info.entries if entry.sha256 == shared_digest)
    assert shared.kind == "artifact"
    assert shared.datasets == ("fixture:first@1", "fixture:second@2")
    registry = next(entry for entry in info.entries if entry.sha256 == index_digest)
    assert registry.kind == "registry"
    assert registry.registry_release == "cache-test-1"
    assert registry.datasets == ()


def test_cache_info_marks_corrupt_content_invalid(tmp_path: Path) -> None:
    _, _, other_digest = _write_cache_fixture(tmp_path)
    (tmp_path / "objects" / "sha256" / other_digest).write_bytes(b"corrupt")

    info = cache_info(cache_dir=tmp_path)

    other = next(entry for entry in info.entries if entry.sha256 == other_digest)
    assert not other.valid
    assert other.size == len(b"corrupt")


def test_cache_clean_filters_by_age_and_reports_active_objects(
    tmp_path: Path,
) -> None:
    _, shared_digest, other_digest = _write_cache_fixture(tmp_path)
    shared_path = tmp_path / "objects" / "sha256" / shared_digest
    old = shared_path.stat().st_mtime - 2 * 24 * 60 * 60
    os.utime(shared_path, (old, old))

    with _reader_lease(tmp_path, "objects", shared_digest):
        result = cache_clean(cache_dir=tmp_path, older_than=timedelta(days=1))

    assert result.removed == ()
    assert [entry.sha256 for entry in result.skipped] == [shared_digest]
    assert shared_path.is_file()
    assert (tmp_path / "objects" / "sha256" / other_digest).is_file()

    result = cache_clean(cache_dir=tmp_path, older_than=timedelta(days=1))

    assert [entry.sha256 for entry in result.removed] == [shared_digest]
    assert result.bytes_removed == len(b"shared artifact")
    assert result.skipped == ()
    assert not shared_path.exists()


def test_cache_clean_removes_a_dataset_or_the_entire_cache(tmp_path: Path) -> None:
    index_digest, shared_digest, other_digest = _write_cache_fixture(tmp_path)

    selected = cache_clean(cache_dir=tmp_path, dataset="fixture:first@1")

    assert [entry.sha256 for entry in selected.removed] == [shared_digest]
    assert (tmp_path / "objects" / "sha256" / other_digest).is_file()
    assert (tmp_path / "registries" / "sha256" / index_digest).is_file()

    remaining = cache_clean(cache_dir=tmp_path)

    assert {entry.sha256 for entry in remaining.removed} == {
        index_digest,
        other_digest,
    }
    assert cache_info(cache_dir=tmp_path).entries == ()


def test_cache_clean_rejects_a_negative_age(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        cache_clean(cache_dir=tmp_path, older_than=timedelta(seconds=-1))


def test_cache_clean_requires_a_canonical_dataset_identifier(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="canonical"):
        cache_clean(cache_dir=tmp_path, dataset="fixture:first")


def test_publishers_and_readers_share_a_lease_that_excludes_cleaners(
    tmp_path: Path,
) -> None:
    with (
        _publisher_lease(tmp_path, "objects", _DIGEST),
        _reader_lease(tmp_path, "objects", _DIGEST),
        _cleaner_lease(tmp_path, "objects", _DIGEST) as acquired,
    ):
        assert not acquired

    with _cleaner_lease(tmp_path, "objects", _DIGEST) as acquired:
        assert acquired


def test_concurrent_processes_publish_atomically_while_cleaner_skips(
    tmp_path: Path,
) -> None:
    contents = b"concurrent publication"
    digest = hashlib.sha256(contents).hexdigest()
    requests_ready = threading.Event()
    may_respond = threading.Event()
    request_count = 0
    request_count_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            nonlocal request_count
            with request_count_lock:
                request_count += 1
                if request_count == 2:
                    requests_ready.set()
            assert may_respond.wait(timeout=5)
            self.send_response(200)
            self.send_header("Content-Length", str(len(contents)))
            self.end_headers()
            self.wfile.write(contents)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    host, port = server.server_address
    script = """
import sys
from pathlib import Path
from datamonger._cache import verified_download
from datamonger.errors import ArtifactIntegrityError

path = verified_download(
    cache_root=Path(sys.argv[1]),
    namespace="objects",
    url=sys.argv[2],
    digest=sys.argv[3],
    size=int(sys.argv[4]),
    integrity_error=ArtifactIntegrityError,
)
print(path)
"""
    command = [
        sys.executable,
        "-c",
        script,
        os.fspath(tmp_path),
        f"http://{host}:{port}/artifact",
        digest,
        str(len(contents)),
    ]
    processes = [
        subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        for _ in range(2)
    ]
    try:
        assert requests_ready.wait(timeout=5)
        target = tmp_path / "objects" / "sha256" / digest
        assert not target.exists()
        with _cleaner_lease(tmp_path, "objects", digest) as acquired:
            assert not acquired
        may_respond.set()
        outputs = [process.communicate(timeout=5) for process in processes]
    finally:
        may_respond.set()
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        server.shutdown()
        server_thread.join()
        server.server_close()

    assert all(process.returncode == 0 for process in processes), outputs
    assert request_count == 2
    assert len({stdout.strip() for stdout, _ in outputs}) == 1
    assert target.read_bytes() == contents


def test_abrupt_process_exit_leaves_a_reclaimable_lease_record(
    tmp_path: Path,
) -> None:
    script = """
import os
import sys
from pathlib import Path
from datamonger._cache import _publisher_lease

with _publisher_lease(Path(sys.argv[1]), "objects", sys.argv[2]):
    print("leased", flush=True)
    os._exit(23)
"""
    process = subprocess.run(
        [sys.executable, "-c", script, os.fspath(tmp_path), _DIGEST],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert process.stdout.strip() == "leased"
    assert process.returncode == 23

    lease_path = tmp_path / ".leases" / "objects" / "sha256" / f"{_DIGEST}.lock"
    assert lease_path.is_file()
    with _cleaner_lease(tmp_path, "objects", _DIGEST) as acquired:
        assert acquired
