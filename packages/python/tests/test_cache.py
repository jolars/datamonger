from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from datamonger._cache import _cleaner_lease, _publisher_lease, _reader_lease

_DIGEST = "a" * 64


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
