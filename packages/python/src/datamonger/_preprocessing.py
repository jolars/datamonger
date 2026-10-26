"""Validate descriptive processing history without applying transformations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from datamonger._errors import UnsupportedRegistryError
from datamonger._validate import require_array, require_mapping, require_string


def preprocessing_metadata(dataset: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if "preprocessing" not in dataset:
        return None
    if dataset.get("schema_version") not in (3, 4, 5):
        raise UnsupportedRegistryError("preprocessing requires manifest schema 3 or 4")

    def nonempty(value: object, field: str) -> str:
        text = require_string(value, field, UnsupportedRegistryError)
        if not text:
            raise UnsupportedRegistryError(f"{field} must not be empty")
        return text

    metadata = require_mapping(
        dataset["preprocessing"], "preprocessing", UnsupportedRegistryError
    )
    if metadata.keys() != {"upstream", "datamonger"}:
        raise UnsupportedRegistryError("preprocessing requires exactly two stages")
    for name, raw in metadata.items():
        stage = require_mapping(raw, f"preprocessing.{name}", UnsupportedRegistryError)
        if stage.keys() - {"status", "steps", "evidence", "notes"}:
            raise UnsupportedRegistryError("unknown preprocessing stage field")
        status = stage.get("status")
        if status not in ("unknown", "none", "documented"):
            raise UnsupportedRegistryError("unsupported preprocessing status")
        if "notes" in stage:
            nonempty(stage["notes"], "preprocessing notes")
        if status != "unknown" and "evidence" not in stage:
            raise UnsupportedRegistryError("known preprocessing requires evidence")
        if "evidence" in stage:
            evidence = require_array(
                stage["evidence"], "preprocessing evidence", UnsupportedRegistryError
            )
            if not evidence:
                raise UnsupportedRegistryError(
                    "preprocessing evidence must not be empty"
                )
            for reference in evidence:
                nonempty(reference, "preprocessing evidence reference")
        if status != "documented":
            if "steps" in stage:
                raise UnsupportedRegistryError("only documented processing has steps")
            continue
        steps = require_array(
            stage.get("steps"), "preprocessing steps", UnsupportedRegistryError
        )
        if not steps:
            raise UnsupportedRegistryError("documented preprocessing requires steps")
        for raw_step in steps:
            step = require_mapping(
                raw_step, "preprocessing step", UnsupportedRegistryError
            )
            if step.keys() - {"kind", "description", "parameters"}:
                raise UnsupportedRegistryError("unknown preprocessing step field")
            kind = nonempty(step.get("kind"), "preprocessing kind")
            if re.fullmatch(r"[a-z0-9][a-z0-9._-]*", kind) is None:
                raise UnsupportedRegistryError("invalid preprocessing kind")
            nonempty(step.get("description"), "preprocessing description")
            if "parameters" in step:
                parameters = require_mapping(
                    step["parameters"],
                    "preprocessing parameters",
                    UnsupportedRegistryError,
                )
                for key, value in parameters.items():
                    nonempty(key, "preprocessing parameter name")
                    nonempty(value, "preprocessing parameter value")
    return dict(metadata)
