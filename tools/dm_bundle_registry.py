"""Adopt a published registry snapshot in all four clients."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).resolve().parents[1]
_VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
BUNDLE_DIRECTORIES = (
    Path("packages/cli/assets"),
    Path("packages/python/src/datamonger/_data"),
    Path("packages/r/inst/extdata"),
    Path("packages/julia/src/data"),
)


def fetch_index(url: str) -> bytes:
    """Retrieve the public release asset without depending on a local gh login."""
    request = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.geturl().startswith("https://"):
            raise ValueError("published index redirected away from HTTPS")
        return cast(bytes, response.read())


def _replace(text: str, pattern: str, replacement: str, path: Path) -> str:
    result, count = re.subn(pattern, lambda _: replacement, text, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"expected exactly one bundled registry declaration in {path}")
    return result


def bundle(root: Path, release: str | None = None, *, check_only: bool = False) -> None:
    """Validate every output before checking or updating the client snapshots."""
    root = root.resolve()
    current = json.loads((root / BUNDLE_DIRECTORIES[0] / "selector.json").read_bytes())
    if release is None:
        release = current["release"]
    if not isinstance(release, str) or not _VERSION.fullmatch(release):
        raise ValueError("registry release must be a stable semantic version")
    if not check_only and tuple(map(int, release.split("."))) < tuple(
        map(int, current["release"].split("."))
    ):
        raise ValueError("refusing to downgrade the bundled registry")

    directory = root / "registry/releases" / release
    selector_bytes = (directory / "selector.json").read_bytes()
    selector = json.loads(selector_bytes)
    schema = json.loads((root / "spec/schema/selector-v1.schema.json").read_bytes())
    Draft202012Validator(schema).validate(selector)
    url = selector["index_url"]
    if selector["release"] != release or url != (
        "https://github.com/jolars/datamonger/releases/download/"
        f"registry-v{release}/index.json"
    ):
        raise ValueError("selector does not identify the requested GitHub release")
    index = (directory / "index.json").read_bytes()
    digest = selector["index_sha256"]
    if hashlib.sha256(index).hexdigest() != digest:
        raise ValueError("local index digest does not match selector")
    record = json.loads(index)
    if (
        record.get("release") != release
        or type(record.get("schema_version")) is not int
        or record.get("schema_version") not in (1, 2)
    ):
        raise ValueError("index release or schema does not match selector")

    outputs = {directory / "index.json": index for directory in BUNDLE_DIRECTORIES}
    outputs[BUNDLE_DIRECTORIES[0] / "selector.json"] = selector_bytes
    declarations = {
        Path("packages/python/src/datamonger/_registry.py"): (
            r"BUNDLED_REGISTRY = Registry\(.*?\n\)",
            f'BUNDLED_REGISTRY = Registry(\n    release="{release}",\n'
            f'    index_sha256="{digest}",\n'
            "    index_url=(\n"
            '        "https://github.com/jolars/datamonger/releases/download/"\n'
            f'        "registry-v{release}/index.json"\n    ),\n)',
        ),
        Path("packages/r/R/registry.R"): (
            r"\.bundled_registry <- \.new_registry\(.*?\n\)",
            f'.bundled_registry <- .new_registry(\n  release = "{release}",\n'
            f'  index_sha256 = "{digest}",\n'
            "  index_url = paste0(\n"
            '    "https://github.com/jolars/datamonger/releases/download/",\n'
            f'    "registry-v{release}/index.json"\n  )\n)',
        ),
        Path("packages/julia/src/registry.jl"): (
            r"const BUNDLED_REGISTRY = Registry\(.*?\n\)",
            f'const BUNDLED_REGISTRY = Registry(\n    "{release}",\n'
            f'    "{digest}",\n    "{url}",\n)',
        ),
        Path("README.md"): (
            r"<!-- bundled-registry:start -->.*?<!-- bundled-registry:end -->",
            "<!-- bundled-registry:start -->\n"
            f"All four clients bundle the stable `{release}` snapshot. "
            "Its selector is\n"
            f"[`registry/releases/{release}/selector.json`]"
            f"(registry/releases/{release}/selector.json).\n"
            "<!-- bundled-registry:end -->",
        ),
    }
    for path, (pattern, replacement) in declarations.items():
        outputs[path] = _replace(
            (root / path).read_text(encoding="utf-8"), pattern, replacement, path
        ).encode("utf-8")

    changed = [
        path for path, data in outputs.items() if (root / path).read_bytes() != data
    ]
    if check_only:
        if changed:
            raise ValueError(
                "bundled registry files are stale: " + ", ".join(map(str, changed))
            )
        return
    # An unpublished snapshot must never become a package's default trust root.
    if fetch_index(url) != index:
        raise ValueError(
            "published index does not match the local snapshot and selector"
        )
    for path in changed:
        (root / path).write_bytes(outputs[path])
    print(f"Bundled registry {release}: updated {len(changed)} files.")


def main() -> int:
    """Run the client bundle update or the offline consistency check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", nargs="?")
    parser.add_argument(
        "--check",
        action="store_true",
        help="check offline; default to the bundled release",
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if not args.check and args.release is None:
        parser.error("release is required when updating bundles")
    try:
        bundle(args.root, args.release, check_only=args.check)
    except (OSError, ValueError, ValidationError) as error:
        print(f"dm-bundle-registry: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
