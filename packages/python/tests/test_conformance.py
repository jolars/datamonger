from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

import pytest
from conftest import CORPUS, LIBSVM_OPTIONS, OPTIONS
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from datamonger._canonical import canonical_sha256
from datamonger._decode import decode_delimited_text
from datamonger._decode_libsvm import decode_libsvm, decode_libsvm_split
from datamonger.errors import (
    ArtifactIntegrityError,
    ArtifactUnavailableError,
    CacheError,
    DecodedIntegrityError,
    DecodeError,
    OfflineError,
    RetrievalLocationsError,
    UnknownDatasetError,
    UnsupportedDecoderError,
    UnsupportedRegistryError,
)


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
        inputs = case["input"]
        if isinstance(inputs, str):
            assert (CORPUS / inputs).is_file()
        else:
            assert isinstance(inputs, dict)
            assert set(inputs) == {"train", "test"}
            assert all((CORPUS / str(path)).is_file() for path in inputs.values())
        assert case["expected_sha256"] is not None


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in load_cases("cases.json")
        if case["area"] == "delimited-text" and case["status"] == "active-python"
    ],
    ids=lambda case: case["id"],
)
def test_active_delimited_text_cases_match_golden_digest(
    case: dict[str, object],
) -> None:
    recipe = case["recipe"]
    assert isinstance(recipe, dict)

    decoded = decode_delimited_text(CORPUS / str(case["input"]), recipe)

    assert canonical_sha256(decoded.components) == case["expected_sha256"]


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in load_cases("cases.json")
        if case["area"] == "libsvm" and case["status"] == "active-python"
    ],
    ids=lambda case: case["id"],
)
def test_active_libsvm_cases_match_golden_digest(
    case: dict[str, object],
) -> None:
    recipe = case["recipe"]
    assert isinstance(recipe, dict)

    decoded = decode_libsvm(CORPUS / str(case["input"]), recipe)

    assert canonical_sha256(decoded.components) == case["expected_sha256"]


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in load_cases("cases.json")
        if case["area"] == "libsvm-split" and case["status"] == "active-python"
    ],
    ids=lambda case: case["id"],
)
def test_active_libsvm_split_cases_match_golden_digest(
    case: dict[str, object],
) -> None:
    inputs = case["input"]
    recipe = case["recipe"]
    assert isinstance(inputs, dict)
    assert isinstance(recipe, dict)

    decoded = decode_libsvm_split(
        CORPUS / str(inputs["train"]),
        CORPUS / str(inputs["test"]),
        recipe,
    )

    assert canonical_sha256(decoded.components) == case["expected_sha256"]


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


def test_shared_error_cases_map_to_distinct_python_types() -> None:
    cases = load_cases("errors.json")
    python_types = {
        "unknown-dataset": UnknownDatasetError,
        "unsupported-registry": UnsupportedRegistryError,
        "unsupported-decoder": UnsupportedDecoderError,
        "artifact-unavailable": ArtifactUnavailableError,
        "artifact-offline": OfflineError,
        "retrieval-exhausted": RetrievalLocationsError,
        "artifact-integrity": ArtifactIntegrityError,
        "decoded-integrity": DecodedIntegrityError,
        "cache": CacheError,
        "decode": DecodeError,
    }

    assert {case["expected"] for case in cases} == set(python_types)
    assert len(set(python_types.values())) == len(python_types)
    for case in cases:
        assert set(case) == {"id", "expected"}
        assert isinstance(case["id"], str)
        assert python_types[case["expected"]].__module__ == "datamonger._errors"


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
