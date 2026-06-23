from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from .collect_eis import (
        INTERIM_DIR,
        LOG_DIR,
        RAW_DIR,
        Organization,
        build_eis_search_url,
        fetch_url,
        parse_purchase_cards,
        safe_filename,
        write_csv,
    )
except ImportError:
    from collect_eis import (
        INTERIM_DIR,
        LOG_DIR,
        RAW_DIR,
        Organization,
        build_eis_search_url,
        fetch_url,
        parse_purchase_cards,
        safe_filename,
        write_csv,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUERIES = PROJECT_ROOT / "stages" / "stage1" / "config" / "eis_search_queries.csv"


@dataclass
class Query:
    query: str
    notes: str


def read_queries(path: Path) -> list[Query]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [
            Query(query=row["query"].strip(), notes=row.get("notes", "").strip())
            for row in csv.DictReader(fh)
            if row.get("query", "").strip()
        ]


def append_log(row: dict[str, str]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "eis_query_collection_log.csv"
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = {}
    for row in rows:
        key = (row.get("purchase_number"), row.get("source_url"))
        unique[key] = row
    return list(unique.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect broad EIS candidates by Sber-related search queries.")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--from-date", default="2024-01-01")
    parser.add_argument("--to-date", default="2025-12-31")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for item in read_queries(args.queries):
        org = Organization(
            legal_name=item.query,
            short_name=item.query,
            aliases=(item.query,),
            inn="",
            priority="broad",
        )
        for page in range(1, args.pages + 1):
            url = build_eis_search_url(org, args.from_date, args.to_date, page)
            started_at = datetime.now().isoformat(timespec="seconds")
            status = "ok"
            error = ""
            parsed = 0
            try:
                page_html = fetch_url(url)
                raw_path = RAW_DIR / safe_filename(f"query_{item.query}_page_{page}")
                raw_path.write_text(page_html, encoding="utf-8")
                records = parse_purchase_cards(page_html, url, org)
                for record in records:
                    record["query"] = item.query
                    record["query_notes"] = item.notes
                rows.extend(records)
                parsed = len(records)
            except OSError as exc:
                status = "error"
                error = str(exc)

            append_log(
                {
                    "started_at": started_at,
                    "source": "EIS",
                    "query": item.query,
                    "page": str(page),
                    "status": status,
                    "records": str(parsed),
                    "error": error,
                    "url": url,
                }
            )
            time.sleep(args.sleep)

    rows = dedupe(rows)
    broad_rows = write_csv(INTERIM_DIR / "eis_broad_purchase_candidates.csv", rows)
    strict_rows = write_csv(
        INTERIM_DIR / "eis_broad_purchase_index.csv",
        [row for row in rows if row.get("is_customer_match") == "1"],
    )
    print(f"Wrote {broad_rows} records to {INTERIM_DIR / 'eis_broad_purchase_candidates.csv'}")
    print(f"Wrote {strict_rows} records to {INTERIM_DIR / 'eis_broad_purchase_index.csv'}")


if __name__ == "__main__":
    main()

