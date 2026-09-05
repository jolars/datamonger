"""Load shared language-neutral conformance cases for Python tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

CORPUS = Path(__file__).resolve().parents[3] / "tests" / "conformance"
CASES = json.loads((CORPUS / "cases.json").read_bytes())["cases"]
CASE_BY_ID = {case["id"]: case for case in CASES}

_CSV = cast(dict[str, Any], CASE_BY_ID["delimited-mixed-csv"])
_LIBSVM = cast(dict[str, Any], CASE_BY_ID["libsvm-small"])
_LIBSVM_SPLIT = cast(dict[str, Any], CASE_BY_ID["libsvm-split-small"])

FIXTURE = CORPUS / cast(str, _CSV["input"])
LIBSVM_FIXTURE = CORPUS / cast(str, _LIBSVM["input"])
EXPECTED_DIGEST = cast(str, _CSV["expected_sha256"])
LIBSVM_DIGEST = cast(str, _LIBSVM["expected_sha256"])
LIBSVM_SPLIT_DIGEST = cast(str, _LIBSVM_SPLIT["expected_sha256"])
OPTIONS = cast(dict[str, object], _CSV["recipe"])
LIBSVM_OPTIONS = cast(dict[str, object], _LIBSVM["recipe"])


def _case_input_paths(case: dict[str, Any]) -> tuple[Path, ...]:
    inputs = case["input"]
    if isinstance(inputs, dict):
        return tuple(CORPUS / cast(str, path) for path in inputs.values())
    return (CORPUS / cast(str, inputs),)


_CONFORMANCE_ARTIFACTS = {
    path for case in CASES for path in _case_input_paths(case)
}
CONFORMANCE_ARTIFACTS_BY_SHA256 = {
    hashlib.sha256(path.read_bytes()).hexdigest(): path
    for path in _CONFORMANCE_ARTIFACTS
}
