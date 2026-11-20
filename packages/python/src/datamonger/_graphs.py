"""Graph recipes and table materialization."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from datamonger import _native
from datamonger._decode import _make_dataframe, decode_delimited_text
from datamonger._decoder_options import delimited_options
from datamonger._errors import UnsupportedDecoderError
from datamonger._models import DecodedGraph, GraphDataset, HypergraphDataset

_HIF_TABLES = ("nodes", "hyperedges", "incidences")


def _object(value: object, fields: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise UnsupportedDecoderError(f"expected graph recipe fields {sorted(fields)}")
    return value


def _hif_columns(
    value: object, reserved: set[str]
) -> tuple[list[tuple[str, str]], bool]:
    options = _object(value, {"weight", "attributes"})
    weight, attributes = options["weight"], options["attributes"]
    if type(weight) is not bool or not isinstance(attributes, list):
        raise UnsupportedDecoderError("invalid HIF columns")
    names = reserved | ({"weight"} if weight else set())
    columns = []
    for attribute in attributes:
        column = _object(attribute, {"name", "type"})
        name, kind = column["name"], column["type"]
        if (
            not isinstance(name, str)
            or not name
            or name in names
            or kind not in ("int64", "float64", "string", "bool")
        ):
            raise UnsupportedDecoderError("invalid or duplicate HIF attribute")
        names.add(name)
        columns.append((name, kind))
    return columns, weight


def validate_graph_options(
    decoder: str, value: object, artifacts: Sequence[Mapping[str, Any]]
) -> Mapping[str, Any]:
    for artifact in artifacts:
        if artifact.get("compression") not in ("none", "gzip", "bzip2"):
            raise UnsupportedDecoderError("unsupported graph artifact compression")
    if decoder == "graph-tables":
        options = _object(value, {"directed", "nodes", "edges"})
        for role, artifact in zip(("nodes", "edges"), artifacts, strict=True):
            table = options[role]
            if not isinstance(table, Mapping):
                raise UnsupportedDecoderError("expected graph table options")
            _, _, delimiter = delimited_options(table)
            if {"csv": ",", "tsv": "\t"}.get(str(artifact.get("format"))) != delimiter:
                raise UnsupportedDecoderError(
                    "graph table format and delimiter disagree"
                )
    else:
        options = _object(value, {"directed", "node_id", "edge_id", *_HIF_TABLES})
        if artifacts[0].get("format") != "hif" or any(
            options[key] not in ("int64", "string") for key in ("node_id", "edge_id")
        ):
            raise UnsupportedDecoderError("invalid HIF artifact format or ID type")
        tables = tuple(
            _hif_columns(options[role], reserved)
            for role, reserved in zip(
                _HIF_TABLES,
                ({"id"}, {"id"}, {"node", "edge", "direction"}),
                strict=True,
            )
        )
        options = {**options, **dict(zip(_HIF_TABLES, tables, strict=True))}
    if type(options["directed"]) is not bool:
        raise UnsupportedDecoderError("directed must be a boolean")
    return options


def decode_graph(
    decoder: str,
    paths: Sequence[Path],
    options: Mapping[str, Any],
    compressions: Sequence[str],
) -> DecodedGraph:
    directed = options["directed"]
    if decoder == "graph-tables":
        nodes, edges = (
            decode_delimited_text(path, options[role], compression=compression)
            for role, path, compression in zip(
                ("nodes", "edges"), paths, compressions, strict=True
            )
        )
        components = _native.assemble_graph(
            directed, nodes.components, edges.components
        )
        return DecodedGraph(
            GraphDataset(directed, nodes.data, edges.data), tuple(components)
        )
    components = _native.decode_hif(
        paths[0],
        compressions[0],
        (
            directed,
            options["node_id"],
            options["edge_id"],
            options["nodes"],
            options["hyperedges"],
            options["incidences"],
        ),
    )
    node_frame, hyperedges, incidences = (
        _make_dataframe(
            tuple(
                replace(component, name=component.name.removeprefix(role + "/"))
                for component in components
                if component.name.startswith(role + "/")
            )
        )
        for role in _HIF_TABLES
    )
    return DecodedGraph(
        HypergraphDataset(directed, node_frame, hyperedges, incidences),
        tuple(components),
    )
