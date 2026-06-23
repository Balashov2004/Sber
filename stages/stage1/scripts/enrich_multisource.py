from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ANON_DIR = PROJECT_ROOT / "data" / "processed" / "anonymized"
ORGS_PATH = PROJECT_ROOT / "stages" / "stage1" / "config" / "sber_organizations_seed.csv"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "stage1"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def direct_eis_url(number: str) -> str:
    return (
        "https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html"
        f"?regNumber={number}"
    )


def main() -> None:
    ast_rows = read_csv(ANON_DIR / "sberbank_ast_purchase_index.csv")
    eis_rows = read_csv(ANON_DIR / "eis_broad_purchase_index.csv")
    orgs = read_csv(ORGS_PATH)
    org_by_inn = {row["inn"]: row for row in orgs if row.get("inn")}

    eis_by_number: dict[str, dict[str, str]] = {}
    for row in eis_rows:
        number = row.get("purchase_number", "")
        if number:
            eis_by_number[number] = row

    enriched: list[dict[str, object]] = []
    links: list[dict[str, object]] = []
    linked_eis: set[str] = set()

    for row in ast_rows:
        number = row.get("purchCode", "")
        customer_inn = row.get("CustomerInn", "")
        org = org_by_inn.get(customer_inn, {})
        eis = eis_by_number.get(number)
        source_systems = ["Sberbank-AST"]
        if eis:
            source_systems.append("EIS")
            linked_eis.add(number)
            links.append(
                {
                    "canonical_purchase_id": f"purchase:{number}",
                    "left_source": "Sberbank-AST",
                    "left_record_id": number,
                    "right_source": "EIS",
                    "right_record_id": number,
                    "match_method": "exact_purchase_number",
                    "match_confidence": 1.0,
                    "left_url": row.get("objectHrefTerm", ""),
                    "right_url": direct_eis_url(number),
                }
            )
        enriched.append(
            {
                "canonical_purchase_id": f"purchase:{number}",
                "purchase_number": number,
                "source_count": len(source_systems),
                "source_systems": "|".join(source_systems),
                "primary_source": "Sberbank-AST",
                "title": row.get("purchName") or row.get("BidName", ""),
                "customer_name": row.get("CustomerFullName", ""),
                "customer_inn": customer_inn,
                "customer_kpp": org.get("kpp", ""),
                "customer_ogrn": org.get("ogrn", ""),
                "relation_to_sber": org.get("relation_to_sber", ""),
                "organization_verification_source": org.get("source", ""),
                "publication_date": row.get("PublicDate", ""),
                "application_end_date": row.get("RequestDate") or row.get("EndDate", ""),
                "amount": row.get("purchAmount", ""),
                "currency": row.get("purchCurrency", ""),
                "status": row.get("PurchaseStageTerm") or row.get("BidStatusName") or row.get("purchStateName", ""),
                "procedure_type": row.get("PurchaseTypeName", ""),
                "platform_section": row.get("SourceTerm", ""),
                "region": row.get("RegionName", ""),
                "sberbank_ast_url": row.get("objectHrefTerm", ""),
                "eis_url": direct_eis_url(number) if eis else "",
                "eis_law": eis.get("law", "") if eis else "",
                "eis_amount_text": eis.get("amount_text", "") if eis else "",
                "link_quality": "exact_purchase_number" if eis else "single_source",
            }
        )

    for number, eis in eis_by_number.items():
        if number in linked_eis:
            continue
        customer_inn = eis.get("customer_seed_inn", "")
        org = org_by_inn.get(customer_inn, {})
        enriched.append(
            {
                "canonical_purchase_id": f"purchase:{number}",
                "purchase_number": number,
                "source_count": 1,
                "source_systems": "EIS",
                "primary_source": "EIS",
                "title": eis.get("snippet", ""),
                "customer_name": eis.get("extracted_customer", ""),
                "customer_inn": customer_inn,
                "customer_kpp": org.get("kpp", ""),
                "customer_ogrn": org.get("ogrn", ""),
                "relation_to_sber": org.get("relation_to_sber", ""),
                "organization_verification_source": org.get("source", ""),
                "publication_date": eis.get("first_date_seen", ""),
                "amount": eis.get("amount_text", ""),
                "status": eis.get("status_text", ""),
                "eis_url": direct_eis_url(number),
                "eis_law": eis.get("law", ""),
                "link_quality": "single_source",
            }
        )

    stats = {
        "canonical_purchases": len(enriched),
        "linked_source_pairs": len(links),
        "multi_source_purchases": sum(int(row["source_count"]) > 1 for row in enriched),
        "single_source_purchases": sum(int(row["source_count"]) == 1 for row in enriched),
        "organization_enriched_rows": sum(bool(row.get("customer_ogrn")) for row in enriched),
        "sources_used": ["Sberbank-AST", "EIS", "FNS EGRUL"],
        "link_methods": {"exact_purchase_number": len(links)},
    }
    write_csv(OUT_DIR / "purchases_multisource_enriched.csv", enriched)
    write_csv(OUT_DIR / "source_links.csv", links)
    (OUT_DIR / "enrichment_report.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
