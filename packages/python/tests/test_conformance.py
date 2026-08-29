from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

import pytest
from conftest import CORPUS, LIBSVM_OPTIONS, OPTIONS
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm
from datamonger.errors import DecodeError


def load_cases(name: str) -> list[dict[str, object]]:
    document = json.loads((CORPUS / name).read_bytes())
    assert document["schema_version"] == 1
    cases = document["cases"]
    assert isinstance(cases, list)
    assert all(isinstance(case, dict) for case in cases)
    return cases


def test_shared_decoder_case_descriptors_are_closed_and_resolvable() -> None:
    cases = load_cases("cases.json")
    identifiers = [case["id"] for case in cases]

    assert len(identifiers) == len(set(identifiers))
    for case in cases:
        assert set(case) == {
            "id",
            "area",
            "status",
            "input",
            "recipe",
            "expected_sha256",
        }
        assert case["status"] in {"active-python", "milestone-3"}
        assert (CORPUS / str(case["input"])).is_file()
        assert case["expected_sha256"] is not None


def test_canonical_case_descriptors_have_exact_hex_golden_values() -> None:
    cases = load_cases("canonical/cases.json")
    identifiers = [case["id"] for case in cases]

    assert len(identifiers) == len(set(identifiers))
    for case in cases:
        assert set(case) == {"id", "component", "expected_hex"}
        expected = case["expected_hex"]
        assert isinstance(expected, str)
        assert expected == expected.lower()
        assert bytes.fromhex(expected).startswith(b"DMCF\x01\x00")


@pytest.mark.parametrize(
    "case", load_cases("fuzz-regressions.json"), ids=lambda c: c["id"]
)
def test_committed_fuzz_regressions_are_decode_errors(
    case: dict[str, object], tmp_path: Path
) -> None:
    artifact = tmp_path / "fuzz-input"
    artifact.write_bytes(bytes.fromhex(str(case["input_hex"])))

    with pytest.raises(DecodeError):
        if case["decoder"] == "delimited-text":
            decode_delimited_text(
                artifact,
                OPTIONS | {"columns": [{"name": "x", "type": "string"}]},
            )
        else:
            decode_libsvm(artifact, LIBSVM_OPTIONS)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(raw=st.binary(max_size=96))
def test_arbitrary_libsvm_bytes_never_escape_the_decoder_contract(
    raw: bytes, tmp_path: Path
) -> None:
    artifact = tmp_path / "random.libsvm"
    artifact.write_bytes(raw)

    with suppress(DecodeError):
        decode_libsvm(artifact, LIBSVM_OPTIONS)
