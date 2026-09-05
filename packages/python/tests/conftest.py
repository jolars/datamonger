"""Load shared language-neutral conformance cases for Python tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

CORPUS = Path(__file__).resolve().parents[3] / "tests" / "conformance"
CASES = json.loads((CORPUS / "cases.json").read_bytes())["cases"]
CASE_BY_ID = {case["id"]: case for case in CASES}

_CSV = cast(dict[str, Any], CASE_BY_ID["delimited-mixed-csv"])
_TSV = cast(dict[str, Any], CASE_BY_ID["delimited-mixed-tsv"])
_LIBSVM = cast(dict[str, Any], CASE_BY_ID["libsvm-small"])
_SVMLIGHT = cast(dict[str, Any], CASE_BY_ID["svmlight-small"])
_LIBSVM_SPLIT = cast(dict[str, Any], CASE_BY_ID["libsvm-split-small"])

FIXTURE = CORPUS / cast(str, _CSV["input"])
TSV_FIXTURE = CORPUS / cast(str, _TSV["input"])
LIBSVM_FIXTURE = CORPUS / cast(str, _LIBSVM["input"])
SVMLIGHT_FIXTURE = CORPUS / cast(str, _SVMLIGHT["input"])
EXPECTED_DIGEST = cast(str, _CSV["expected_sha256"])
LIBSVM_DIGEST = cast(str, _LIBSVM["expected_sha256"])
LIBSVM_SPLIT_DIGEST = cast(str, _LIBSVM_SPLIT["expected_sha256"])
OPTIONS = cast(dict[str, object], _CSV["recipe"])
LIBSVM_OPTIONS = cast(dict[str, object], _LIBSVM["recipe"])

CONFORMANCE_ARTIFACTS_BY_SHA256 = {
    "8a46d390c070778b3617d11ba9a0ea0cb3516a2c54aeafdc53c9196367208c1e": FIXTURE,
    "6fd6c20b84a335c8de0d7163722b20e2f3a95f1d61a6bea4395670e05f81e044": (TSV_FIXTURE),
    "621fd6e613189956bfea3db00e1413608c793b42001b5d75d55c87382acd4ba6": (
        LIBSVM_FIXTURE
    ),
    "db6007bff9efaa468f44c20b485a51f92d794141dae44a490ac83aa721e7cb36": (
        SVMLIGHT_FIXTURE
    ),
}
