from collections.abc import Sequence
from pathlib import Path

from datamonger._models import LogicalValueComponent

def decode_delimited(
    path: Path,
    columns: Sequence[tuple[str, str]],
    missing_values: Sequence[str],
    delimiter: str,
    compression: str,
) -> list[LogicalValueComponent]: ...
def decode_libsvm(
    train: tuple[Path, str],
    test: tuple[Path, str] | None,
    recipe: tuple[int, str, str],
    decoder_version: int,
    compute_digest: bool,
) -> tuple[list[LogicalValueComponent], str | None]: ...
def canonical_bytes(components: Sequence[LogicalValueComponent]) -> bytes: ...
def canonical_sha256(components: Sequence[LogicalValueComponent]) -> str: ...
