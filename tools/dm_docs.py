"""Install public assets, catalog metadata, and shared markup in the documentation."""

import argparse
import re
from contextlib import suppress
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from shutil import copy2


def install(documentation: Path) -> None:
    """Complete a Diplodocus build with the website's shared assets and navigation."""
    site = documentation / "site"
    pages = sorted(site.rglob("*.html"))
    if not pages:
        raise SystemExit("Build documentation/site before installing public assets.")
    generated = documentation / "generated/datasets"
    if not (generated / "catalog.json").is_file():
        raise SystemExit(
            "Generate the dataset catalog with python tools/dm_catalog.py."
        )
    minisearch = documentation / "node_modules/minisearch"
    if not (minisearch / "dist/es/index.js").is_file():
        raise SystemExit(
            "Install website dependencies with npm ci --prefix documentation."
        )

    markup = (documentation / "head.html").read_text(encoding="utf-8")
    start = "<!-- Datamonger shared head -->"
    end = "<!-- End Datamonger shared head -->"
    block = f"{start}\n{markup}{end}\n"
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if start in html:
            before, rest = html.split(start, 1)
            _, after = rest.split(end, 1)
            html = before + after.removeprefix("\n")
        if "</head>" not in html:
            raise ValueError(f"Missing </head> in {page}")
        is_dataset = page.is_relative_to(site / "datasets")

        def navigation(match: re.Match[str], is_dataset: bool = is_dataset) -> str:
            links = re.sub(
                r'<li class="catalog-nav">.*?</li>', "", match[2], flags=re.DOTALL
            )
            if is_dataset:
                links = links.replace(' aria-current="true"', "")
            current = ' aria-current="true"' if is_dataset else ""
            catalog_link = (
                '<li class="catalog-nav"><a href="/datasets/"'
                f"{current}>Datasets</a></li>"
            )
            links = links.replace("</li>", "</li>" + catalog_link, 1)
            return match[1] + links + match[3]

        html = re.sub(
            r'(<nav class="global-nav [^"]+"[^>]*><ul>)(.*?)(</ul></nav>)',
            navigation,
            html,
            flags=re.DOTALL,
        )
        page.write_text(html.replace("</head>", block + "</head>", 1), encoding="utf-8")

    for asset in (documentation / "public").iterdir():
        copy2(asset, site / asset.name)
    copy2(minisearch / "dist/es/index.js", site / "minisearch.js")
    copy2(minisearch / "LICENSE.txt", site / "minisearch.LICENSE.txt")
    for metadata in generated.rglob("*.json"):
        if metadata.name.startswith("."):
            continue
        target = site / "datasets" / metadata.relative_to(generated)
        target.parent.mkdir(parents=True, exist_ok=True)
        copy2(metadata, target)
    print(f"Installed public assets and shared head markup in {len(pages)} pages.")


class PreviewHandler(SimpleHTTPRequestHandler):
    """Resolve the clean page URLs used by the deployed static site."""

    def translate_path(self, path: str) -> str:
        target = super().translate_path(path)
        if not Path(target).exists() and Path(target + ".html").is_file():
            return target + ".html"
        return target


def serve(documentation: Path, port: int) -> None:
    """Preview the completed files, including assets installed after rendering."""
    handler = partial(PreviewHandler, directory=str(documentation / "site"))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Serving http://127.0.0.1:{server.server_port}", flush=True)
        with suppress(KeyboardInterrupt):
            server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve", action="store_true", help="preview the completed site"
    )
    parser.add_argument("--port", type=int, default=8001)
    arguments = parser.parse_args()
    documentation = Path(__file__).resolve().parents[1] / "documentation"
    install(documentation)
    if arguments.serve:
        serve(documentation, arguments.port)


if __name__ == "__main__":
    main()
