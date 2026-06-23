from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCES = PROJECT_ROOT / "stages" / "stage1" / "config" / "source_probe_urls.csv"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "source_probes"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "source_probe_results.csv"
LINKS_PATH = PROJECT_ROOT / "data" / "interim" / "source_probe_links.csv"


@dataclass
class Source:
    source: str
    url: str
    kind: str


def read_sources(path: Path) -> list[Source]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [
            Source(
                source=row["source"].strip(),
                url=row["url"].strip(),
                kind=row.get("kind", "").strip(),
            )
            for row in csv.DictReader(fh)
            if row.get("url", "").strip()
        ]


def fetch_url(url: str) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 procurement-research/0.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.geturl(), response.read().decode(charset, errors="replace")


def safe_filename(source: Source, final_url: str) -> str:
    digest = hashlib.sha1(final_url.encode("utf-8")).hexdigest()[:10]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{source.source}_{source.kind}")[:80]
    return f"{name}_{digest}.html"


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def extract_links(page_html: str, base_url: str, source_name: str) -> list[dict[str, str]]:
    rows = []
    tokens = ["закуп", "торг", "сбер", "223", "44", "api", "search", "export", "download", "list", "purchase"]
    for href, text in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", page_html, flags=re.I | re.S):
        clean_text = strip_tags(text)
        full_url = urljoin(base_url, html.unescape(href.strip()))
        haystack = f"{clean_text} {full_url}".lower()
        if any(token in haystack for token in tokens):
            rows.append(
                {
                    "source": source_name,
                    "text": clean_text[:300],
                    "url": full_url,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return 0
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe procurement source home pages and record accessible links.")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    probe_rows: list[dict[str, str]] = []
    link_rows: list[dict[str, str]] = []

    for source in read_sources(args.sources):
        started_at = datetime.now().isoformat(timespec="seconds")
        status = "ok"
        final_url = ""
        size = 0
        error = ""
        try:
            http_status, final_url, page_html = fetch_url(source.url)
            size = len(page_html)
            (RAW_DIR / safe_filename(source, final_url)).write_text(page_html, encoding="utf-8")
            link_rows.extend(extract_links(page_html, final_url, source.source))
            status = str(http_status)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            status = "error"
            error = str(exc)

        probe_rows.append(
            {
                "started_at": started_at,
                "source": source.source,
                "kind": source.kind,
                "url": source.url,
                "final_url": final_url,
                "status": status,
                "size": str(size),
                "error": error,
            }
        )

    write_csv(OUT_PATH, probe_rows)
    write_csv(LINKS_PATH, link_rows)
    print(f"Wrote {len(probe_rows)} probe rows to {OUT_PATH}")
    print(f"Wrote {len(link_rows)} link rows to {LINKS_PATH}")


if __name__ == "__main__":
    main()

