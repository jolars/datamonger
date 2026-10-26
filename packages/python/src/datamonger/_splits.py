"""Named split assembly using the existing single-artifact decoders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from datamonger._errors import UnsupportedDecoderError
from datamonger._models import (
    DatasetSplits,
    DecodedSparseDataset,
    DecodedSplits,
    DecodedTable,
)


def component_name(split: str, component: str) -> str:
    """Escape each path segment so arbitrary provider names remain distinct."""
    return "/".join(s.replace("~", "~0").replace("/", "~1") for s in (split, component))


def split_recipes(representation: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    """Validate the assembly before any artifact retrieval."""
    fail = UnsupportedDecoderError
    if (
        type(representation.get("decoder_version")) is not int
        or representation["decoder_version"] != 1
    ):
        raise fail("unsupported named-splits version")
    options = representation.get("options")
    inputs = representation.get("inputs")
    if not isinstance(options, Mapping) or set(options) != {"splits"}:
        raise fail("named-splits options must contain exactly splits")
    splits = options["splits"]
    if not isinstance(splits, list) or not splits:
        raise fail("splits must be a nonempty array")
    names: set[str] = set()
    for split in splits:
        if not isinstance(split, Mapping) or set(split) != {
            "name",
            "decoder",
            "decoder_version",
            "options",
        }:
            raise fail("invalid split recipe fields")
        name = split["name"]
        if not isinstance(name, str) or not name or name in names:
            raise fail("split names must be nonempty and unique")
        names.add(name)
        if (
            split["decoder"] not in ("delimited-text", "libsvm")
            or type(split["decoder_version"]) is not int
            or split["decoder_version"]
            not in ((1, 2) if split["decoder"] == "libsvm" else (1,))
            or not isinstance(split["options"], Mapping)
        ):
            raise fail("unsupported split decoder recipe")
    if not isinstance(inputs, Mapping) or set(inputs) != names:
        raise fail("input names must match the declared split names")
    return tuple(splits)


def assemble_splits(
    recipes: Sequence[Mapping[str, Any]],
    decoded: Sequence[DecodedTable | DecodedSparseDataset],
) -> DecodedSplits:
    pairs = tuple(zip(recipes, decoded, strict=True))
    return DecodedSplits(
        data=DatasetSplits({recipe["name"]: child.data for recipe, child in pairs}),
        components=tuple(
            replace(component, name=component_name(recipe["name"], component.name))
            for recipe, child in pairs
            for component in child.components
        ),
    )
