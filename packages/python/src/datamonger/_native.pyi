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
    path: Path,
    feature_count: int,
    label_type: str,
    target_name: str,
    compression: str,
) -> list[LogicalValueComponent]: ...
def canonical_bytes(components: Sequence[LogicalValueComponent]) -> bytes: ...
def canonical_sha256(components: Sequence[LogicalValueComponent]) -> str: ...
