from __future__ import annotations

import argparse
import csv
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = PROJECT_ROOT / "data" / "external" / "cbr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 procurement-research/1.0",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def collect_usd(from_date: str, to_date: str) -> list[dict[str, object]]:
    params = urllib.parse.urlencode(
        {
            "date_req1": datetime.strptime(from_date, "%Y-%m-%d").strftime("%d/%m/%Y"),
            "date_req2": datetime.strptime(to_date, "%Y-%m-%d").strftime("%d/%m/%Y"),
            "VAL_NM_RQ": "R01235",
        }
    )
    url = "https://www.cbr.ru/scripts/XML_dynamic.asp?" + params
    root = ET.fromstring(fetch(url))
    rows = []
    for record in root.findall("Record"):
        nominal = int(record.findtext("Nominal", "1"))
        value = float(record.findtext("Value", "0").replace(",", "."))
        rows.append(
            {
                "date": datetime.strptime(record.attrib["Date"], "%d.%m.%Y").date().isoformat(),
                "usd_rub": round(value / nominal, 6),
                "source_url": url,
            }
        )
    return rows


def collect_key_rate(from_date: str, to_date: str) -> list[dict[str, object]]:
    from_ru = datetime.strptime(from_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    to_ru = datetime.strptime(to_date, "%Y-%m-%d").strftime("%d.%m.%Y")
    query = urllib.parse.urlencode(
        {
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": from_ru,
            "UniDbQuery.To": to_ru,
        }
    )
    url = "https://www.cbr.ru/hd_base/KeyRate/?" + query
    page = fetch(url)
    pairs = re.findall(
        r"<td[^>]*>\s*(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>",
        page,
        flags=re.I | re.S,
    )
    return [
        {
            "date": datetime.strptime(date_text, "%d.%m.%Y").date().isoformat(),
            "key_rate": float(rate_text.replace(",", ".")),
            "source_url": url,
        }
        for date_text, rate_text in pairs
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect official CBR external factors.")
    parser.add_argument("--from-date", default="2024-01-01")
    parser.add_argument("--to-date", default="2025-12-31")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    usd = collect_usd(args.from_date, args.to_date)
    key_rate = collect_key_rate(args.from_date, args.to_date)
    write_csv(args.out_dir / "usd_rub_daily.csv", usd)
    write_csv(args.out_dir / "key_rate_daily.csv", key_rate)
    print(f"USD/RUB rows: {len(usd)}")
    print(f"Key-rate rows: {len(key_rate)}")


if __name__ == "__main__":
    main()
