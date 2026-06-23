from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ORGS = PROJECT_ROOT / "stages" / "stage1" / "config" / "sber_organizations_seed.csv"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "eis" / "search_pages"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
LOG_DIR = PROJECT_ROOT / "logs"


@dataclass
class Organization:
    legal_name: str
    short_name: str
    aliases: tuple[str, ...]
    inn: str
    priority: str


def read_organizations(path: Path) -> list[Organization]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = csv.DictReader(fh)
        return [
            Organization(
                legal_name=row.get("legal_name", "").strip(),
                short_name=row.get("short_name", "").strip(),
                aliases=tuple(
                    item.strip()
                    for item in row.get("aliases", "").split("|")
                    if item.strip()
                ),
                inn=row.get("inn", "").strip(),
                priority=row.get("priority", "").strip(),
            )
            for row in rows
        ]


def build_eis_search_url(org: Organization, from_date: str, to_date: str, page: int) -> str:
    """Build an EIS extended-search URL for 223-FZ/44-FZ procurement cards.

    EIS does not publish a stable public REST API for this use case, so the
    first collector stores search-page snapshots and parses visible card data.
    Parameters are intentionally explicit and easy to adjust if EIS changes.
    """
    search_value = org.inn or org.legal_name
    params = {
        "searchString": search_value,
        "morphology": "on",
        "search-filter": "Дате размещения",
        "pageNumber": page,
        "sortDirection": "false",
        "recordsPerPage": "_50",
        "showLotsInfoHidden": "false",
        "fz44": "on",
        "fz223": "on",
        "publishDateFrom": to_eis_date(from_date),
        "publishDateTo": to_eis_date(to_date),
    }
    return "https://zakupki.gov.ru/epz/order/extendedsearch/results.html?" + urlencode(params)


def to_eis_date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")


def fetch_url(url: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 procurement-research/0.1",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def safe_filename(value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:80] + "_" + digest + ".html"


def strip_tags(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_text(value: str) -> str:
    value = value.upper().replace("Ё", "Е")
    value = re.sub(r"[\"'«»“”]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_customer_text(block: str) -> str:
    patterns = [
        r"Организация,\s*осуществляющая\s*размещение\s*(.+?)\s*Начальная\s+цена",
        r"Заказчик\s*(.+?)\s*Начальная\s+цена",
        r"Заказчик\s*(.+?)\s*Размещено",
    ]
    for pattern in patterns:
        match = re.search(pattern, block, flags=re.I | re.S)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def matches_customer_scope(customer_text: str, org: Organization) -> tuple[bool, str]:
    normalized_customer = normalize_text(customer_text)
    aliases = org.aliases or (org.legal_name, org.short_name)
    for alias in aliases:
        normalized_alias = normalize_text(alias)
        if normalized_alias and normalized_alias in normalized_customer:
            return True, alias
    return False, ""


def parse_purchase_cards(page_html: str, source_url: str, org: Organization) -> list[dict[str, str]]:
    """Parse visible EIS search cards.

    The parser is deliberately tolerant: it extracts stable purchase numbers
    and nearby text snippets even when exact EIS markup shifts.
    """
    records: list[dict[str, str]] = []
    blocks = re.split(r"(?=№\s*\d{8,})", strip_tags(page_html))
    for block in blocks:
        number_match = re.search(r"№\s*(\d{8,})", block)
        if not number_match:
            continue

        customer_text = extract_customer_text(block)
        is_customer_match, matched_alias = matches_customer_scope(customer_text, org)

        amount_match = re.search(r"([\d\s]+(?:[,.]\d{1,2})?)\s*(?:₽|руб)", block, flags=re.I)
        date_match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", block)
        law_match = re.search(r"\b(44-ФЗ|223-ФЗ)\b", block)
        status_match = re.search(r"\b(Подача заявок|Работа комиссии|Закупка завершена|Отменена|Размещение завершено)\b", block)

        records.append(
            {
                "purchase_number": number_match.group(1),
                "customer_seed_name": org.legal_name,
                "customer_seed_inn": org.inn,
                "extracted_customer": customer_text,
                "matched_alias": matched_alias,
                "is_customer_match": "1" if is_customer_match else "0",
                "match_quality": "customer_or_organizer_text_match" if is_customer_match else "candidate_text_search_only",
                "law": law_match.group(1) if law_match else "",
                "first_date_seen": date_match.group(1) if date_match else "",
                "amount_text": amount_match.group(0) if amount_match else "",
                "status_text": status_match.group(1) if status_match else "",
                "snippet": block[:1000],
                "source_url": source_url,
            }
        )
    return records


def write_csv(path: Path, rows: Iterable[dict[str, str]]) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return 0
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def append_log(row: dict[str, str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "collection_log.csv"
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect Sber procurement search pages from EIS.")
    parser.add_argument("--orgs", type=Path, default=DEFAULT_ORGS)
    parser.add_argument("--from-date", default="2024-01-01")
    parser.add_argument("--to-date", default="2025-12-31")
    parser.add_argument("--pages", type=int, default=1, help="Pages per organization for the first pass.")
    parser.add_argument("--sleep", type=float, default=1.5, help="Delay between requests.")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned URLs.")
    args = parser.parse_args()

    organizations = read_organizations(args.orgs)
    candidates: list[dict[str, str]] = []

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    for org in organizations:
        if not (org.inn or org.legal_name):
            continue
        for page in range(1, args.pages + 1):
            url = build_eis_search_url(org, args.from_date, args.to_date, page)
            if args.dry_run:
                print(json.dumps({"organization": org.legal_name, "inn": org.inn, "url": url}, ensure_ascii=False))
                continue

            started_at = datetime.now().isoformat(timespec="seconds")
            status = "ok"
            error = ""
            record_count = 0
            try:
                page_html = fetch_url(url)
                raw_path = RAW_DIR / safe_filename(f"{org.inn or org.legal_name}_page_{page}")
                raw_path.write_text(page_html, encoding="utf-8")
                records = parse_purchase_cards(page_html, url, org)
                candidates.extend(records)
                record_count = sum(1 for record in records if record["is_customer_match"] == "1")
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                status = "error"
                error = str(exc)

            append_log(
                {
                    "started_at": started_at,
                    "source": "EIS",
                    "organization": org.legal_name,
                    "inn": org.inn,
                    "page": str(page),
                    "status": status,
                    "records": str(record_count),
                    "error": error,
                    "url": url,
                }
            )
            time.sleep(args.sleep)

    if not args.dry_run:
        index = [record for record in candidates if record["is_customer_match"] == "1"]
        candidate_rows_written = write_csv(INTERIM_DIR / "eis_purchase_candidates.csv", candidates)
        rows_written = write_csv(INTERIM_DIR / "eis_purchase_index.csv", index)
        print(f"Wrote {candidate_rows_written} records to {INTERIM_DIR / 'eis_purchase_candidates.csv'}")
        print(f"Wrote {rows_written} records to {INTERIM_DIR / 'eis_purchase_index.csv'}")


if __name__ == "__main__":
    main()
