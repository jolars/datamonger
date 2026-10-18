from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from datamonger import Registry, _api, cite_data, data_info
from datamonger.errors import UnknownDatasetError, UnsupportedRegistryError

REFERENCES = [
    {"citation": "Dataset deposit.", "role": "dataset", "recommended": True},
    {
        "citation": "Collection paper.",
        "role": "paper",
        "recommended": True,
        "note": "Describes the observations.",
    },
    {"citation": "Benchmark collection.", "role": "collection", "recommended": False},
    {"citation": "Other reference."},
]


@pytest.fixture
def citation_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Registry, dict[str, Any]]:
    index = json.loads(
        (Path(__file__).parents[1] / "src/datamonger/_data/index.json").read_bytes()
    )
    dataset = next(d for d in index["datasets"] if d["name"] == "iris")
    index["schema_version"] = dataset["schema_version"] = 2
    dataset["provenance"]["citations"] = REFERENCES
    dataset["provenance"]["citation_instructions"] = "Please cite both references."
    selected = Registry("citation-test", "a" * 64, "https://example.invalid/index")
    monkeypatch.setattr(_api, "_load_registry", lambda *_args, **_kwargs: index)
    return selected, dataset


def test_cite_data_selects_upstream_recommendations_and_preserves_all_metadata(
    citation_registry: tuple[Registry, dict[str, Any]],
) -> None:
    registry, _ = citation_registry
    info = data_info("uci:iris@1", registry=registry, offline=True)
    assert info.citations == tuple(REFERENCES)
    assert info.citation_instructions == "Please cite both references."
    assert info.registry_release == "citation-test"
    assert cite_data("uci:iris@1", registry=registry, format="records") == tuple(
        REFERENCES[:2]
    )
    assert cite_data(
        "uci:iris",
        registry=registry,
        format="records",
        include_all=True,
    ) == tuple(REFERENCES)
    text = cite_data("iris", source="uci", registry=registry)
    assert "[dataset] Dataset deposit." in text
    assert "[paper] Collection paper.\nDescribes the observations." in text
    assert "Please cite both references." in text
    assert "Benchmark" not in text
    assert "[collection] Benchmark" in cite_data(
        "uci:iris", registry=registry, include_all=True
    )


def test_legacy_citation_and_unknown_recommendations_are_explicit(
    citation_registry: tuple[Registry, dict[str, Any]],
) -> None:
    registry, dataset = citation_registry
    dataset["schema_version"] = 1
    dataset["provenance"] = {"citation": "Legacy citation."}
    assert cite_data("uci:iris", registry=registry, format="records") == (
        {"citation": "Legacy citation."},
    )
    assert cite_data("uci:iris", registry=registry) == (
        "No upstream citation recommendation is recorded.\n\nLegacy citation."
    )
    dataset["schema_version"] = 2
    dataset["provenance"] = {"citations": [{"citation": "Unclassified reference."}]}
    assert "No upstream citation recommendation" in cite_data(
        "uci:iris", registry=registry
    )


def test_missing_citations_and_explicitly_unrecommended_references(
    citation_registry: tuple[Registry, dict[str, Any]],
) -> None:
    registry, dataset = citation_registry
    dataset["provenance"] = {}
    assert cite_data("uci:iris", registry=registry, format="records") == ()
    assert (
        cite_data("uci:iris", registry=registry) == "No citation metadata is recorded."
    )
    dataset["provenance"] = {"citations": [REFERENCES[2]]}
    assert cite_data("uci:iris", registry=registry, format="records") == ()
    assert (
        cite_data("uci:iris", registry=registry)
        == "No references are marked as recommended."
    )
    assert cite_data(
        "uci:iris", registry=registry, include_all=True, format="records"
    ) == (REFERENCES[2],)


@pytest.mark.parametrize(
    "record",
    [
        {"citation": ""},
        {"citation": 12},
        {"citation": "Text", "role": []},
        {"citation": "Text", "role": "method"},
        {"citation": "Text", "note": None},
        {"citation": "Text", "recommended": 1},
        {"citation": "Text", "extra": True},
    ],
)
def test_invalid_citation_records_use_registry_errors(
    citation_registry: tuple[Registry, dict[str, Any]],
    record: dict[str, Any],
) -> None:
    registry, dataset = citation_registry
    dataset["provenance"] = {"citations": [record]}
    with pytest.raises(UnsupportedRegistryError):
        cite_data("uci:iris", registry=registry)


def test_cite_data_forwards_registry_selection_and_offline_loading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    citation_registry: tuple[Registry, dict[str, Any]],
) -> None:
    registry, _ = citation_registry
    loader = _api._load_registry
    calls = []

    def load(selected: Registry, cache: Path, *, offline: bool) -> Any:
        calls.append((selected, cache, offline))
        return loader(selected, cache, offline=offline)

    monkeypatch.setattr(_api, "_load_registry", load)
    cite_data("uci:iris", registry=registry, cache_dir=tmp_path, offline=True)
    assert calls == [(registry, tmp_path, True)]
    with pytest.raises(UnknownDatasetError):
        cite_data("uci:missing", registry=registry)
    with pytest.raises(ValueError, match="format"):
        cite_data("uci:iris", registry=registry, format="bibtex")  # type: ignore[call-overload]
    assert len(calls) == 2
