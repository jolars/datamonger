"""Shared fixture files, golden digests, and decoder options."""

from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"
LIBSVM_FIXTURE = Path(__file__).parent / "fixtures" / "small.libsvm"
EXPECTED_DIGEST = "e25d27e8b0008332d778cd48429a7c4f7af59411884092e52f120da63f26e726"
LIBSVM_DIGEST = "50b077922f6ffc77054622fd807fbc8de48d1c3fcb3be644027422b244b0190b"

OPTIONS = {
    "encoding": "utf-8",
    "delimiter": ",",
    "header": True,
    "quote": '"',
    "escape": "double",
    "missing_values": [""],
    "row_order": "source",
    "columns": [
        {"name": "measurement", "type": "float64"},
        {"name": "count", "type": "int64"},
        {"name": "label", "type": "string"},
        {"name": "enabled", "type": "bool"},
    ],
}

LIBSVM_OPTIONS = {
    "index_base": 1,
    "feature_count": 4,
    "duplicate_features": "error",
    "label_type": "int64",
    "row_order": "source",
    "target_name": "response",
}
