"""Generate the website's dataset catalog from a pinned registry snapshot."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypedDict, cast
from urllib.parse import quote, urlsplit

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTOR = Path("packages/cli/assets/selector.json")
DEFAULT_OUTPUT = Path("documentation/generated/datasets")
COMPONENT_LIMIT = 30


class Dimension(TypedDict):
    task: str | None
    type: str | None
    split: str | None
    samples: int | None
    predictors: int | None


class Entry(TypedDict):
    id: str
    source: str
    name: str
    version: str
    title: str
    description: str
    authors: list[str]
    tasks: list[str]
    dimensions: list[Dimension]
    storage: str
    download_bytes: int | None
    license: str
    default: bool
    url: str


def _identity(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return record["source"], record["name"], record["version"]


def load_snapshot(
    root: Path, selector_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check the selector, exact index digest, schemas, and default identities."""
    schemas = {
        path.name: json.loads(path.read_bytes())
        for path in (root / "spec/schema").glob("*.schema.json")
    }
    resources: Registry[Any] = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )

    def validate(record: object, schema: str) -> None:
        Draft202012Validator(
            schemas[schema], registry=resources, format_checker=FormatChecker()
        ).validate(record)

    selector = json.loads((root / selector_path).read_bytes())
    validate(selector, "selector-v1.schema.json")
    index_bytes = (
        root / "registry/releases" / selector["release"] / "index.json"
    ).read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != selector["index_sha256"]:
        raise ValueError("registry index digest does not match the selector")
    index = json.loads(index_bytes)
    schema_version = index.get("schema_version")
    if type(schema_version) is not int or schema_version not in (1, 2, 3, 4, 5):
        raise ValueError("unsupported registry index schema")
    validate(index, f"index-v{schema_version}.schema.json")
    if index["release"] != selector["release"]:
        raise ValueError("registry release does not match the selector")
    identities = [_identity(record) for record in index["datasets"]]
    defaults = [_identity(record) for record in index["defaults"]]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate dataset identity")
    if len({identity[:2] for identity in defaults}) != len(defaults):
        raise ValueError("duplicate default dataset")
    if not set(defaults) <= set(identities):
        raise ValueError("default dataset is missing from the index")
    return cast(dict[str, Any], selector), cast(dict[str, Any], index)


def dimensions(dataset: Mapping[str, Any]) -> list[Dimension]:
    """Keep each task's feature count and each split's sample count together."""
    components = {
        component["name"]: component
        for component in dataset["representation"]["expect"]["components"]
    }
    result: list[Dimension] = []
    for task in dataset.get("tasks", []):
        for split, binding in sorted(task.get("splits", {"": task}).items()):
            features = binding["features"]
            predictors = (
                len(features)
                if isinstance(features, list)
                else components[features].get("columns")
            )
            target = components[binding["target"]]
            result.append(
                {
                    "task": task["name"],
                    "type": task["type"],
                    "split": split or None,
                    "samples": target.get("length", target.get("rows")),
                    "predictors": predictors,
                }
            )
    if not result:
        # A representation has variables, but only a task identifies predictors.
        lengths = {
            component.get("length", component.get("rows"))
            for component in components.values()
        }
        result.append(
            {
                "task": None,
                "type": None,
                "split": None,
                "samples": lengths.pop() if len(lengths) == 1 else None,
                "predictors": None,
            }
        )
    return result


def summarize(dataset: Mapping[str, Any], *, default: bool) -> Entry:
    """Project a registry record into the small fields used by the browser."""
    source, name, version = _identity(dataset)
    sizes = [artifact.get("size") for artifact in dataset["artifacts"]]
    license_record = dataset["license"]
    return {
        "id": f"{source}:{name}@{version}",
        "source": source,
        "name": name,
        "version": version,
        "title": dataset["title"],
        "description": dataset["description"],
        "authors": dataset["provenance"].get("authors", []),
        "tasks": sorted({task["type"] for task in dataset.get("tasks", [])}),
        "dimensions": dimensions(dataset),
        "storage": (
            "sparse"
            if any(
                component["kind"] == "sparse_matrix"
                for component in dataset["representation"]["expect"]["components"]
            )
            else "dense"
        ),
        "download_bytes": sum(sizes)
        if all(size is not None for size in sizes)
        else None,
        "license": (
            license_record.get("identifier", "Known (see terms)")
            if license_record["status"] == "known"
            else "Unknown"
        ),
        "default": default,
        "url": f"/datasets/{source}/{name}/{quote(version, safe='')}",
    }


def _text(value: object) -> str:
    # Diplodocus resolves HTTPS links, but does not accept the DOI URI scheme.
    prose = re.sub(r"\bdoi:(10\.\d{4,9}/\S+)", r"https://doi.org/\1", str(value))
    text = html.escape(prose, quote=False).replace("\n", " ")
    return re.sub(r"([\\`*_{}\[\]#|])", r"\\\1", text)


def _link(label: str, url: str, *, local: bool = False) -> str:
    if not local and urlsplit(url).scheme not in {"http", "https"}:
        return f"{_text(label)}: {_text(url)}"
    destination = quote(url, safe="/#%._-" if local else "/:#?&=%@!$'+,;~-._")
    return f"[{_text(label)}](<{destination}>)"


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [headers, ["---"] * len(headers), *rows]
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in lines)


def _count(value: int | None) -> str:
    return f"{value:,}" if value is not None else "Unknown"


def _range(entry: Entry, field: Literal["samples", "predictors"]) -> str:
    values = {
        dimension[field]
        for dimension in entry["dimensions"]
        if dimension[field] is not None
    }
    counts = cast(set[int], values)
    if not counts:
        return "Unknown"
    if len(counts) == 1:
        return _count(counts.pop())
    return f"{min(counts):,}\u2013{max(counts):,}"


def _size(value: int | None) -> str:
    if value is None:
        return "Unknown"
    for unit, scale in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if value >= scale:
            return f"{value / scale:,.1f} {unit}"
    return f"{value:,} B"


def browser_page(entries: Sequence[Entry], selector: Mapping[str, Any]) -> str:
    rows = [
        [
            _link(
                entry["title"],
                entry["url"].removeprefix("/datasets/") + ".md",
                local=True,
            ),
            _text(entry["source"]),
            ", ".join(entry["tasks"]) or "No task specified",
            _range(entry, "samples"),
            _range(entry, "predictors"),
            _size(entry["download_bytes"]),
            _text(entry["license"]),
        ]
        for entry in entries
        if entry["default"]
    ]
    return (
        "# Datasets\n\n"
        "Find research datasets to use with Datamonger in Python, R, Julia, "
        "or the CLI. Open a dataset for its provenance, variables, citations, "
        "and retrieval examples.\n\n"
        f"Registry **{_text(selector['release'])}**, matching the clients' bundled "
        f"snapshot. {len(rows)} default dataset versions. "
        + _link("Download the registry selector", "selector.json", local=True)
        + ".\n\n"
        "## Browse datasets\n\n"
        + _table(
            [
                "Dataset",
                "Source",
                "Task",
                "Samples",
                "Predictors",
                "Download",
                "License",
            ],
            rows,
        )
        + "\n\nCounts refer to individual tasks and splits. A range shows differences "
        "between them. Predictor counts exclude targets and identifiers. "
        "Unknown values have not been established by the registry. "
        "Download sizes include all registered artifacts in their distributed form.\n"
    )


def _retrieval(entry: Entry, selector: Mapping[str, Any]) -> str:
    release, digest, url = (
        selector[field] for field in ("release", "index_sha256", "index_url")
    )
    reference = entry["id"]
    python = (
        "from datamonger import Registry, fetch_data\n\n"
        "registry = Registry(\n"
        f"    release={json.dumps(release)},\n"
        f"    index_sha256={json.dumps(digest)},\n"
        f"    index_url={json.dumps(url)},\n"
        ")\n"
        f"data = fetch_data({json.dumps(reference)}, registry=registry)"
    )
    r = (
        "library(datamonger)\n\n"
        "registry <- registry_selector(\n"
        f"  release = {json.dumps(release)},\n"
        f"  index_sha256 = {json.dumps(digest)},\n"
        f"  index_url = {json.dumps(url)}\n"
        ")\n"
        f"data <- fetch_data({json.dumps(reference)}, registry = registry)"
    )
    julia = (
        "using Datamonger\n\n"
        "registry = registry_selector(\n"
        f"    {json.dumps(release)},\n"
        f"    {json.dumps(digest)},\n"
        f"    {json.dumps(url)},\n"
        ")\n"
        f"data = fetch_data({json.dumps(reference)}; registry=registry)"
    )
    cli = (
        "cat > datamonger-registry.json <<'JSON'\n"
        + json.dumps(dict(selector), ensure_ascii=False, indent=2, sort_keys=True)
        + "\nJSON\n"
        f"datamonger --selector datamonger-registry.json fetch '{reference}'"
    )
    panels = "\n\n".join(
        f"### {label}\n\n```{language}\n{code}\n```"
        for label, language, code in (
            ("Python", "python", python),
            ("R", "r", r),
            ("Julia", "julia", julia),
            ("CLI", "sh", cli),
        )
    )
    return (
        "## Retrieve\n\n"
        "These examples pin both the dataset version and the registry's exact index. "
        "An uncached dataset requires network access to its source. "
        "The CLI retrieves verified artifacts. "
        "The language clients also decode them.\n\n"
        '::: {.panel-tabset group="language"}\n\n' + panels + "\n\n:::\n"
    )


def dataset_page(
    dataset: Mapping[str, Any],
    entry: Entry,
    entries: Sequence[Entry],
    selector: Mapping[str, Any],
    errata: Sequence[Mapping[str, Any]],
) -> str:
    """Render human-readable metadata without expanding wide variable lists."""
    lines = [
        f"# {_text(entry['title'])}",
        _link("Browse datasets", "../../index.md", local=True),
        f"`{entry['id']}` · Registry `{selector['release']}`. "
        + (
            "Default version in this registry."
            if entry["default"]
            else "Other version."
        ),
        _text(entry["description"]),
        "## Dimensions and tasks",
        _table(
            ["Task", "Type", "Split", "Samples", "Predictors"],
            [
                [
                    _text(dimension["task"] or "No task specified"),
                    _text(dimension["type"] or "—"),
                    _text(dimension["split"] or "—"),
                    _count(dimension["samples"]),
                    _count(dimension["predictors"]),
                ]
                for dimension in entry["dimensions"]
            ],
        ),
        "Predictor counts follow each task's feature selection and exclude targets "
        "and identifiers. Sample counts are reported separately for each split.",
        _retrieval(entry, selector),
        "## Representation and variables",
    ]
    representation = dataset["representation"]
    components = representation["expect"]["components"]
    lines.extend(
        [
            f"{_text(dataset['modality']).capitalize()} data with a {entry['storage']} "
            f"representation. Decoder: `{representation['decoder']}` "
            f"version {representation['decoder_version']}.",
            _table(
                ["Component", "Kind", "Type", "Shape"],
                [
                    [
                        _text(component["name"]),
                        _text(component["kind"]),
                        _text(component["type"]),
                        (
                            f"{component['rows']:,} \u00d7 {component['columns']:,}"
                            if "rows" in component
                            else _count(component["length"])
                        ),
                    ]
                    for component in components[:COMPONENT_LIMIT]
                ],
            ),
        ]
    )
    record_link = _link(
        "complete registry record", entry["version"] + ".json", local=True
    )
    if len(components) > COMPONENT_LIMIT:
        lines.append(
            f"Showing {COMPONENT_LIMIT} of {len(components):,} components. "
            f"The {record_link} contains every variable name and task binding."
        )
    lines.append("## Preprocessing")
    preprocessing = dataset.get("preprocessing")
    if preprocessing is None:
        lines.append("Preprocessing history is not recorded in this registry release.")
    else:
        for key, label in (("upstream", "Upstream"), ("datamonger", "Datamonger")):
            stage = preprocessing[key]
            lines.extend([f"### {label}", f"Status: {_text(stage['status'])}."])
            if stage.get("notes"):
                lines.append(_text(stage["notes"]))
            for step in stage.get("steps", []):
                lines.append(f"**{_text(step['kind'])}.** {_text(step['description'])}")
                if step.get("parameters"):
                    lines.append(
                        "Parameters: "
                        + "; ".join(
                            f"{_text(key)}: {_text(value)}"
                            for key, value in sorted(step["parameters"].items())
                        )
                        + "."
                    )
            if stage.get("evidence"):
                lines.append(
                    "Evidence: "
                    + ", ".join(
                        _link(value, value)
                        if urlsplit(value).scheme in {"http", "https"}
                        else _text(value)
                        for value in stage["evidence"]
                    )
                )
    provenance = dataset["provenance"]
    lines.extend(
        [
            "## Provenance and citation",
            f"Provider: {_text(provenance['provider'])}. "
            f"Upstream name: {_text(provenance['upstream_name'])}. "
            f"Retrieved: {_text(provenance['retrieved_at'])}.",
            _link("Original source", provenance["landing_page"]),
        ]
    )
    if provenance.get("authors"):
        lines.append("Authors: " + ", ".join(map(_text, provenance["authors"])) + ".")
    if provenance.get("citation"):
        lines.append(_text(provenance["citation"]))
    for citation in provenance.get("citations", []):
        label = "Recommended citation. " if citation.get("recommended") else ""
        lines.append(label + _text(citation["citation"]))
        if citation.get("note"):
            lines.append(_text(citation["note"]))
    if provenance.get("citation_instructions"):
        lines.append(_text(provenance["citation_instructions"]))
    license_record = dataset["license"]
    lines.extend(["## License", _text(entry["license"])])
    if license_record.get("url"):
        lines.append(_link("License information", license_record["url"]))
    if license_record.get("evidence"):
        lines.append(_text(license_record["evidence"]))
    lines.extend(
        [
            "## Artifacts",
            f"Total download: {_size(entry['download_bytes'])}. "
            "Sizes describe the distributed files, including any compression.",
            _table(
                [
                    "Artifact",
                    "Format",
                    "Compression",
                    "Size",
                    "Distribution",
                    "Preservation",
                ],
                [
                    [
                        _text(artifact["name"]),
                        _text(artifact["format"]),
                        _text(artifact["compression"]),
                        _size(artifact.get("size")),
                        _text(artifact["distribution"]),
                        _text(
                            artifact.get("preservation", {}).get("status", "unknown")
                        ),
                    ]
                    for artifact in dataset["artifacts"]
                ],
            ),
        ]
    )
    for artifact in dataset["artifacts"]:
        for download in artifact.get("downloads", []):
            lines.append(
                _link(f"{artifact['name']}: {download['kind']}", download["url"])
            )
        preservation = artifact.get("preservation", {})
        if preservation.get("deposit"):
            lines.append(_link("Preservation deposit", preservation["deposit"]))
    versions = [
        other
        for other in entries
        if (other["source"], other["name"]) == (entry["source"], entry["name"])
    ]
    lines.extend(
        [
            "## Versions in this registry",
            ", ".join(
                _link(other["version"], other["version"] + ".md", local=True)
                + (" (default)" if other["default"] else "")
                for other in versions
            ),
        ]
    )
    relevant_errata = [
        erratum
        for erratum in errata
        if _identity(erratum["dataset"]) == _identity(dataset)
    ]
    if relevant_errata:
        lines.extend(
            [
                "## Registry errata",
                "This release records corrections for this dataset. Consult the "
                "complete index before interpreting its verification metadata.",
                "```json\n"
                + json.dumps(relevant_errata, ensure_ascii=False, indent=2)
                + "\n```",
            ]
        )
    lines.extend(
        [
            "## Registry record",
            f"Download the {record_link}, "
            + _link("registry selector", "../../selector.json", local=True)
            + ", or "
            + _link("full registry index", selector["index_url"])
            + ".",
            f"Index SHA-256: `{selector['index_sha256']}`.",
        ]
    )
    return "\n\n".join(lines) + "\n"


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def generate(
    root: Path = ROOT,
    *,
    selector_path: Path = DEFAULT_SELECTOR,
    output: Path | None = None,
) -> dict[Path, bytes]:
    """Generate deterministic pages and metadata without retrieving artifacts."""
    root = root.resolve()
    output = output or root / DEFAULT_OUTPUT
    selector, index = load_snapshot(root, selector_path)
    defaults = {_identity(record) for record in index["defaults"]}
    datasets = sorted(index["datasets"], key=_identity)
    entries = [
        summarize(dataset, default=_identity(dataset) in defaults)
        for dataset in datasets
    ]
    entries.sort(key=lambda entry: (entry["title"].casefold(), entry["id"]))
    by_id = {entry["id"]: entry for entry in entries}
    outputs = {
        Path("index.md"): browser_page(entries, selector).encode("utf-8"),
        Path("selector.json"): _json_bytes(selector),
        Path("catalog.json"): _json_bytes(
            {"schema_version": 1, "registry": selector, "datasets": entries}
        ),
    }
    for dataset in datasets:
        source, name, version = _identity(dataset)
        entry = by_id[f"{source}:{name}@{version}"]
        path = Path(source) / name
        outputs[path / (version + ".md")] = dataset_page(
            dataset, entry, entries, selector, index.get("errata", [])
        ).encode("utf-8")
        outputs[path / (version + ".json")] = _json_bytes(dataset)

    # Remove only files recorded by an earlier generation, never authored content.
    inventory = output / ".catalog-files.json"
    previous = json.loads(inventory.read_bytes()) if inventory.is_file() else []
    for relative in previous:
        stale = output / relative
        if not stale.resolve().is_relative_to(output.resolve()):
            raise ValueError("generated catalog inventory escapes its output directory")
        if Path(relative) not in outputs:
            stale.unlink(missing_ok=True)
    for relative, contents in outputs.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    inventory.write_bytes(_json_bytes(sorted(map(str, outputs))))
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--selector", type=Path, default=DEFAULT_SELECTOR)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        outputs = generate(
            arguments.root, selector_path=arguments.selector, output=arguments.output
        )
    except (OSError, ValueError, KeyError, ValidationError) as error:
        print(f"dm-catalog: {error}", file=sys.stderr)
        return 2
    print(f"Generated {len(outputs)} catalog pages and metadata files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
