"""Normalize curated references without inferring citation recommendations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from datamonger._errors import UnsupportedRegistryError
from datamonger._validate import require_array, require_mapping, require_string


def citation_metadata(
    dataset: Mapping[str, Any],
) -> tuple[tuple[Mapping[str, Any], ...], str | None]:
    provenance = require_mapping(
        dataset.get("provenance", {}), "provenance", UnsupportedRegistryError
    )
    if "citation" in provenance and "citations" in provenance:
        raise UnsupportedRegistryError(
            "provenance cannot contain citation and citations"
        )
    if dataset.get("schema_version") == 1 and (
        "citations" in provenance or "citation_instructions" in provenance
    ):
        raise UnsupportedRegistryError("multiple citations require manifest schema 2")

    def nonempty(value: object, field: str) -> str:
        result = require_string(value, field, UnsupportedRegistryError)
        if not result:
            raise UnsupportedRegistryError(f"{field} must not be empty")
        return result

    instructions = (
        nonempty(provenance["citation_instructions"], "citation instructions")
        if "citation_instructions" in provenance
        else None
    )
    if "citation" in provenance:
        return (
            {"citation": nonempty(provenance["citation"], "citation")},
        ), instructions
    records = []
    for raw in require_array(
        provenance.get("citations", []), "citations", UnsupportedRegistryError
    ):
        record = dict(require_mapping(raw, "citation record", UnsupportedRegistryError))
        if record.keys() - {"citation", "role", "note", "recommended"}:
            raise UnsupportedRegistryError("unknown citation record field")
        nonempty(record.get("citation"), "citation")
        if "role" in record and record["role"] not in (
            "dataset",
            "paper",
            "collection",
        ):
            raise UnsupportedRegistryError("unsupported citation role")
        if "note" in record:
            nonempty(record["note"], "citation note")
        if "recommended" in record and not isinstance(record["recommended"], bool):
            raise UnsupportedRegistryError("citation recommended must be a boolean")
        records.append(record)
    return tuple(records), instructions


def select_citations(
    citations: tuple[Mapping[str, Any], ...], *, include_all: bool
) -> tuple[Mapping[str, Any], ...]:
    if include_all or not any("recommended" in record for record in citations):
        return citations
    return tuple(record for record in citations if record.get("recommended") is True)


def citation_text(
    citations: tuple[Mapping[str, Any], ...],
    selected: tuple[Mapping[str, Any], ...],
    instructions: str | None,
) -> str:
    paragraphs = []
    if instructions is not None:
        paragraphs.append(instructions)
    if not citations:
        paragraphs.append("No citation metadata is recorded.")
    elif not any("recommended" in record for record in citations):
        paragraphs.append("No upstream citation recommendation is recorded.")
    elif not selected:
        paragraphs.append("No references are marked as recommended.")
    for record in selected:
        role = f"[{record['role']}] " if "role" in record else ""
        text = role + str(record["citation"])
        if "note" in record:
            text += "\n" + str(record["note"])
        paragraphs.append(text)
    return "\n\n".join(paragraphs)
