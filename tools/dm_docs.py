"""Install public assets and shared head markup in the generated documentation."""

from pathlib import Path
from shutil import copy2


def main() -> None:
    documentation = Path(__file__).resolve().parents[1] / "documentation"
    site = documentation / "site"
    pages = sorted(site.rglob("*.html"))
    if not pages:
        raise SystemExit("Build documentation/site before installing public assets.")

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
        page.write_text(html.replace("</head>", block + "</head>", 1), encoding="utf-8")

    for asset in (documentation / "public").iterdir():
        copy2(asset, site / asset.name)
    print(f"Installed public assets and shared head markup in {len(pages)} pages.")


if __name__ == "__main__":
    main()
