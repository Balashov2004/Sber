from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT = PROJECT_ROOT / "data" / "interim" / "sberbank_ast_purchase_index.csv"
OUT_JSON = PROJECT_ROOT / "data" / "processed" / "stage1" / "coverage_report.json"
OUT_CSV = PROJECT_ROOT / "data" / "processed" / "stage1" / "coverage_by_organization.csv"


def main() -> None:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    by_year = Counter((row.get("PublicDate") or "")[6:10] for row in rows)
    by_source = Counter(row.get("SourceTerm", "") for row in rows)
    by_org = Counter(
        (
            row.get("CustomerInn", ""),
            row.get("CustomerFullName", ""),
            (row.get("PublicDate") or "")[6:10],
        )
        for row in rows
    )

    org_rows = [
        {"customer_inn": inn, "customer_name": name, "year": year, "purchase_count": count}
        for (inn, name, year), count in sorted(by_org.items(), key=lambda item: (-item[1], item[0]))
    ]
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(org_rows[0]) if org_rows else [])
        writer.writeheader()
        writer.writerows(org_rows)

    report = {
        "verified_procurement_rows": len(rows),
        "unique_records": len(
            {
                row.get("PurchaseId")
                or row.get("Bid_id")
                or row.get("purchCode")
                or row.get("objectHrefTerm")
                for row in rows
            }
        ),
        "by_year": dict(by_year),
        "by_source_section": dict(by_source),
        "organizations_with_rows": len({row.get("CustomerInn") for row in rows if row.get("CustomerInn")}),
        "amount_present_rows": sum(bool(row.get("purchAmount")) for row in rows),
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
