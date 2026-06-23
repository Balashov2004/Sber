from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "egrul_organizations_discovered.csv"


@dataclass(frozen=True)
class EgrulOrganization:
    query: str
    name: str
    inn: str
    kpp: str
    ogrn: str
    address: str
    status: str


def post_query(query: str) -> str:
    payload = urlencode(
        {
            "vyp3CaptchaToken": "",
            "page": "",
            "query": query,
            "region": "",
            "PreventChromeAutocomplete": "",
        }
    ).encode("utf-8")
    request = Request(
        "https://egrul.nalog.ru/",
        data=payload,
        headers={
            "User-Agent": "Mozilla/5.0 procurement-research/0.1",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
    )
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    token = data.get("t")
    if not token:
        raise RuntimeError(f"FNS did not return token for query={query!r}: {data}")
    return token


def fetch_results(token: str) -> dict:
    request = Request(
        f"https://egrul.nalog.ru/search-result/{token}",
        headers={
            "User-Agent": "Mozilla/5.0 procurement-research/0.1",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def discover(query: str, attempts: int = 8) -> list[EgrulOrganization]:
    token = post_query(query)
    last_result: dict = {}
    for _ in range(attempts):
        last_result = fetch_results(token)
        rows = last_result.get("rows") or []
        if rows:
            return [
                EgrulOrganization(
                    query=query,
                    name=row.get("n", ""),
                    inn=row.get("i", ""),
                    kpp=row.get("p", ""),
                    ogrn=row.get("o", ""),
                    address=row.get("a", ""),
                    status=row.get("e", ""),
                )
                for row in rows
            ]
        time.sleep(0.5)
    raise RuntimeError(f"FNS did not return rows for query={query!r}: {last_result}")


def write_csv(path: Path, rows: list[EgrulOrganization]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(EgrulOrganization.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Russian legal entities through the public FNS EGRUL search.")
    parser.add_argument("queries", nargs="+")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    discovered: list[EgrulOrganization] = []
    for query in args.queries:
        try:
            rows = discover(query)
            discovered.extend(rows)
            print(f"{query}: {len(rows)} rows")
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            print(f"{query}: error={exc}")
        time.sleep(args.sleep)

    write_csv(args.out, discovered)
    print(f"Wrote {len(discovered)} rows to {args.out}")


if __name__ == "__main__":
    main()

