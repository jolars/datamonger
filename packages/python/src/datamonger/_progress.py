"""Transient progress for downloads in interactive terminals."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress


@contextmanager
def transfer_progress(
    label: str | None, total: int | None
) -> Iterator[Callable[[int], None] | None]:
    stream = sys.stderr
    if (
        label is None
        or stream is None
        or not getattr(stream, "isatty", lambda: False)()
        or os.environ.get("TERM") == "dumb"
    ):
        yield None
        return

    label = "".join(
        character if character.isprintable() else "?" for character in label
    )
    try:
        width = os.get_terminal_size(stream.fileno()).columns
    except (OSError, ValueError):
        width = 0
    width = (width or 80) - 1

    last_update = float("-inf")
    line_length = 0

    def update(count: int) -> None:
        nonlocal last_update, line_length
        now = time.monotonic()
        if count != total and now - last_update < 0.1:
            return
        last_update = now
        if total is None:
            status = f"{count:,} B"
        else:
            filled = min(20, 20 * count // total) if total else 20
            bar = "#" * filled + "-" * (20 - filled)
            status = f"[{bar}] {count:,}/{total:,} B"
        label_width = max(0, width - len(status) - 1)
        line = f"{label[:label_width]} {status}"[:width].lstrip()
        with suppress(OSError, ValueError):
            stream.write(f"\r{line.ljust(line_length)}")
            stream.flush()
            line_length = len(line)

    try:
        update(0)
        yield update
    finally:
        if line_length:
            with suppress(OSError, ValueError):
                stream.write(f"\r{' ' * line_length}\r")
                stream.flush()
