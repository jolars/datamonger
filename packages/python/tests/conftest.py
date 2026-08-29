"""Load shared language-neutral conformance cases for Python tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

CORPUS = Path(__file__).resolve().parents[3] / "tests" / "conformance"
CASES = json.loads((CORPUS / "cases.json").read_bytes())["cases"]
CASE_BY_ID = {case["id"]: case for case in CASES}

_CSV = cast(dict[str, Any], CASE_BY_ID["delimited-mixed-csv"])
_LIBSVM = cast(dict[str, Any], CASE_BY_ID["libsvm-small"])

FIXTURE = CORPUS / cast(str, _CSV["input"])
LIBSVM_FIXTURE = CORPUS / cast(str, _LIBSVM["input"])
EXPECTED_DIGEST = cast(str, _CSV["expected_sha256"])
LIBSVM_DIGEST = cast(str, _LIBSVM["expected_sha256"])
OPTIONS = cast(dict[str, object], _CSV["recipe"])
LIBSVM_OPTIONS = cast(dict[str, object], _LIBSVM["recipe"])
