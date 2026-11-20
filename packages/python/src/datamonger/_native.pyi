from collections.abc import Sequence
from pathlib import Path

from datamonger._models import LogicalComponent, LogicalValueComponent

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
def decode_libsvm_multilabel(
    path: Path, coding: str, recipe: tuple[int, int, int, str], compute_digest: bool
) -> tuple[list[LogicalValueComponent], str | None]: ...
def decode_svmlight_ranking(
    path: Path, coding: str, recipe: tuple[int, int, str, str], compute_digest: bool
) -> tuple[list[LogicalValueComponent], str | None]: ...
def assemble_graph(
    directed: bool,
    nodes: tuple[LogicalComponent, ...],
    edges: tuple[LogicalComponent, ...],
) -> list[LogicalComponent]: ...
def decode_hif(
    path: Path,
    compression: str,
    recipe: tuple[
        bool,
        str,
        str,
        tuple[list[tuple[str, str]], bool],
        tuple[list[tuple[str, str]], bool],
        tuple[list[tuple[str, str]], bool],
    ],
) -> list[LogicalComponent]: ...
