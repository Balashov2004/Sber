from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "anonymized" / "stage1_purchases_candidates.csv"
DEFAULT_STRICT = PROJECT_ROOT / "data" / "processed" / "anonymized" / "stage1_purchases_strict.csv"
DEFAULT_ORGS = PROJECT_ROOT / "stages" / "stage1" / "config" / "sber_organizations_seed.csv"
DEFAULT_ENRICHED = PROJECT_ROOT / "data" / "processed" / "stage1" / "purchases_multisource_enriched.csv"
DEFAULT_LINKS = PROJECT_ROOT / "data" / "processed" / "stage1" / "source_links.csv"
DEFAULT_OUT = PROJECT_ROOT / "data" / "processed" / "stage2"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_key(value: str | None) -> str:
    value = normalize_space(value).upper().replace("Ё", "Е")
    value = re.sub(r"[\"'«»“”]", "", value)
    return re.sub(r"[^A-ZА-Я0-9]+", " ", value).strip()


def parse_amount(value: str | None) -> str:
    value = normalize_space(value)
    if not value:
        return ""
    value = re.sub(r"[^\d,.-]", "", value).replace(" ", "").replace(",", ".")
    if not value:
        return ""
    try:
        return str(Decimal(value).quantize(Decimal("0.01")))
    except InvalidOperation:
        return ""


def parse_date(value: str | None) -> str:
    value = normalize_space(value)
    if not value:
        return ""
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def first_non_empty(row: dict[str, str], fields: list[str]) -> str:
    for field in fields:
        value = normalize_space(row.get(field))
        if value:
            return value
    return ""


def source_record_id(row: dict[str, str]) -> str:
    return first_non_empty(row, ["purchase_number", "Bid_id", "PurchaseId", "purchCode", "BidNo"])


def normalize_purchase(row: dict[str, str], strict_ids: set[tuple[str, str]]) -> dict[str, object]:
    source = first_non_empty(row, ["source_system"]) or "unknown"
    record_id = source_record_id(row)
    purchase_number = first_non_empty(row, ["purchase_number", "purchCode", "BidNo"])
    title = first_non_empty(row, ["purchName", "BidName", "snippet", "productNames"])
    customer_name = first_non_empty(row, ["extracted_customer", "CustomerFullName", "CustomerNickName"])
    customer_inn = first_non_empty(row, ["customer_seed_inn", "CustomerInn"])
    organizer_name = first_non_empty(row, ["OrgFullName", "OrgName"])
    organizer_inn = first_non_empty(row, ["OrgInn"])
    publication_date = parse_date(first_non_empty(row, ["first_date_seen", "PublicDate", "PublicDateText"]))
    end_date = parse_date(first_non_empty(row, ["EndDate", "RequestDate"]))
    amount = parse_amount(first_non_empty(row, ["amount_text", "purchAmountRUB", "purchAmount"]))
    currency = "RUB" if amount else first_non_empty(row, ["purchCurrency"])
    status = first_non_empty(row, ["status_text", "BidStatusName", "PurchaseStageTerm"])
    law = first_non_empty(row, ["law", "PurchaseTypeName", "SourceTerm"])
    source_url = first_non_empty(row, ["source_url", "objectHrefTerm", "SourceHrefTerm"])
    is_strict = (source, record_id) in strict_ids or row.get("data_layer", "").startswith("strict")
    explicit_target_period = normalize_space(row.get("is_target_period"))
    if explicit_target_period:
        is_target_period = explicit_target_period == "1"
    else:
        is_target_period = bool(publication_date) and publication_date[:4] in {"2024", "2025"}

    signature = "|".join(
        [
            normalize_key(title)[:180],
            customer_inn,
            publication_date,
            amount,
        ]
    )

    return {
        "source_system": source,
        "source_record_id": record_id,
        "purchase_number": purchase_number,
        "title": title,
        "customer_name": customer_name,
        "customer_inn": customer_inn,
        "organizer_name": organizer_name,
        "organizer_inn": organizer_inn,
        "publication_date": publication_date,
        "end_date": end_date,
        "amount_rub": amount,
        "currency": currency,
        "status": status,
        "law_or_section": law,
        "region": first_non_empty(row, ["RegionName", "RegionNameTerm"]),
        "source_url": source_url,
        "match_quality": first_non_empty(row, ["match_quality", "data_layer"]),
        "is_strict_sber_match": "1" if is_strict else "0",
        "is_target_period": "1" if is_target_period else "0",
        "dedupe_signature": signature,
    }


def normalize_organizations(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        output.append(
            {
                "inn": row.get("inn", ""),
                "kpp": row.get("kpp", ""),
                "ogrn": row.get("ogrn", ""),
                "legal_name": row.get("legal_name", ""),
                "short_name": row.get("short_name", ""),
                "aliases": row.get("aliases", ""),
                "relation_to_sber": row.get("relation_to_sber", ""),
                "priority": row.get("priority", ""),
                "verification_source": row.get("source", ""),
                "notes": row.get("notes", ""),
            }
        )
    return output


def normalize_enriched_purchase(row: dict[str, str]) -> dict[str, object]:
    publication_date = parse_date(row.get("publication_date"))
    end_date = parse_date(row.get("application_end_date"))
    amount = parse_amount(row.get("amount"))
    return {
        "canonical_purchase_id": row.get("canonical_purchase_id", ""),
        "purchase_number": row.get("purchase_number", ""),
        "title": normalize_space(row.get("title")),
        "customer_name": normalize_space(row.get("customer_name")),
        "customer_inn": row.get("customer_inn", ""),
        "customer_kpp": row.get("customer_kpp", ""),
        "customer_ogrn": row.get("customer_ogrn", ""),
        "relation_to_sber": row.get("relation_to_sber", ""),
        "publication_date": publication_date,
        "end_date": end_date,
        "amount_rub": amount,
        "currency": row.get("currency") or ("RUB" if amount else ""),
        "status": normalize_space(row.get("status")),
        "procedure_type": normalize_space(row.get("procedure_type")),
        "law_or_section": row.get("eis_law") or row.get("platform_section", ""),
        "platform_section": row.get("platform_section", ""),
        "region": normalize_space(row.get("region")),
        "primary_source": row.get("primary_source", ""),
        "source_count": row.get("source_count", "1"),
        "source_systems": row.get("source_systems", ""),
        "primary_url": row.get("sberbank_ast_url") or row.get("eis_url", ""),
        "sberbank_ast_url": row.get("sberbank_ast_url", ""),
        "eis_url": row.get("eis_url", ""),
        "link_quality": row.get("link_quality", ""),
        "year": publication_date[:4] if publication_date else "",
        "month": publication_date[:7] if publication_date else "",
    }


def build_source_records(
    strict_rows: list[dict[str, str]], canonical_numbers: set[str]
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in strict_rows:
        source = first_non_empty(row, ["source_system"]) or "unknown"
        record_id = source_record_id(row)
        number = first_non_empty(row, ["purchase_number", "purchCode", "BidNo"])
        key = (source, record_id)
        if not record_id or key in seen or number not in canonical_numbers:
            continue
        seen.add(key)
        records.append(
            {
                "canonical_purchase_id": f"purchase:{number}",
                "source_system": source,
                "source_record_id": record_id,
                "purchase_number": number,
                "source_url": first_non_empty(row, ["source_url", "objectHrefTerm", "SourceHrefTerm"]),
                "source_section": first_non_empty(row, ["SourceTerm", "law"]),
                "source_status": first_non_empty(row, ["status_text", "PurchaseStageTerm", "BidStatusName", "purchStateName"]),
                "publication_date": parse_date(first_non_empty(row, ["first_date_seen", "PublicDate"])),
                "amount_rub": parse_amount(first_non_empty(row, ["amount_text", "purchAmount"])),
                "match_quality": first_non_empty(row, ["match_quality", "data_layer"]),
            }
        )
    return records


def build_duplicate_audit(
    links: list[dict[str, str]], source_records: list[dict[str, object]]
) -> list[dict[str, object]]:
    by_key = {
        (str(row["source_system"]), str(row["source_record_id"])): row
        for row in source_records
    }
    rows: list[dict[str, object]] = []
    for link in links:
        right = by_key.get((link.get("right_source", ""), link.get("right_record_id", "")), {})
        rows.append(
            {
                "canonical_purchase_id": link.get("canonical_purchase_id", ""),
                "duplicate_source": link.get("right_source", ""),
                "duplicate_record_id": link.get("right_record_id", ""),
                "kept_source": link.get("left_source", ""),
                "kept_record_id": link.get("left_record_id", ""),
                "duplicate_type": "cross_source_same_purchase",
                "match_method": link.get("match_method", ""),
                "match_confidence": link.get("match_confidence", ""),
                "purchase_number": link.get("right_record_id", ""),
                "publication_date": right.get("publication_date", ""),
                "amount_rub": right.get("amount_rub", ""),
                "source_url": link.get("right_url", ""),
            }
        )
    return rows


def build_document_queue(purchases: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for purchase in purchases:
        for source, card_url in (
            ("Sberbank-AST", str(purchase.get("sberbank_ast_url") or "")),
            ("EIS", str(purchase.get("eis_url") or "")),
        ):
            if not card_url:
                continue
            rows.append(
                {
                    "canonical_purchase_id": purchase.get("canonical_purchase_id", ""),
                    "purchase_number": purchase.get("purchase_number", ""),
                    "source_system": source,
                    "card_url": card_url,
                    "document_url": "",
                    "document_type": "unknown_until_card_crawl",
                    "metadata_status": "card_queued",
                    "download_status": "not_started",
                    "extraction_status": "not_started",
                    "anonymization_status": "not_started",
                    "processing_priority": "high" if float(purchase.get("amount_rub") or 0) >= 10_000_000 else "normal",
                    "processing_idea": "crawl card; enumerate attachments; hash files; extract PDF/DOCX/XLSX text; OCR scans; anonymize; extract participants, winner, final price, requirements and delivery terms",
                }
            )
    return rows


def build_initial_analysis(purchases: list[dict[str, object]]) -> dict[str, object]:
    by_year = Counter(str(row.get("year") or "") for row in purchases)
    by_customer = Counter(str(row.get("customer_name") or "") for row in purchases)
    amounts = [Decimal(str(row["amount_rub"])) for row in purchases if row.get("amount_rub")]
    return {
        "purchase_count": len(purchases),
        "by_year": dict(by_year),
        "amount_present_rows": len(amounts),
        "amount_coverage_pct": round(100 * len(amounts) / len(purchases), 2) if purchases else 0,
        "total_amount_rub": str(sum(amounts, Decimal("0.00"))),
        "top_customers_by_count": [
            {"customer_name": name, "purchase_count": count}
            for name, count in by_customer.most_common(10)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean Stage 1 data and build Stage 2 analytical outputs.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--strict", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--organizations", type=Path, default=DEFAULT_ORGS)
    parser.add_argument("--enriched", type=Path, default=DEFAULT_ENRICHED)
    parser.add_argument("--source-links", type=Path, default=DEFAULT_LINKS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    strict_rows = read_csv(args.strict)
    candidate_rows = read_csv(args.candidates)
    strict_ids = {(row.get("source_system", ""), source_record_id(row)) for row in strict_rows}
    clean_rows = [normalize_enriched_purchase(row) for row in read_csv(args.enriched)]
    canonical_numbers = {str(row["purchase_number"]) for row in clean_rows}
    source_records = build_source_records(strict_rows, canonical_numbers)
    duplicate_rows = build_duplicate_audit(read_csv(args.source_links), source_records)
    review_rows = [
        row
        for row in (normalize_purchase(candidate, strict_ids) for candidate in candidate_rows)
        if row["is_target_period"] == "1" and row["is_strict_sber_match"] != "1"
    ]
    stats = {
        "verified_source_rows": len(source_records),
        "canonical_purchase_rows": len(clean_rows),
        "duplicate_source_rows": len(duplicate_rows),
        "duplicate_rate_pct": round(100 * len(duplicate_rows) / len(source_records), 4) if source_records else 0,
        "duplicate_types": dict(Counter(str(row["duplicate_type"]) for row in duplicate_rows)),
        "multi_source_purchases": len(duplicate_rows),
        "single_source_purchases": len(clean_rows) - len(duplicate_rows),
        "manual_review_candidates": len(review_rows),
        "organizations": len(read_csv(args.organizations)),
    }
    organizations = normalize_organizations(read_csv(args.organizations))
    document_plan = build_document_queue(clean_rows)
    initial_analysis = build_initial_analysis(clean_rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "purchases_clean.csv", clean_rows)
    write_csv(args.out_dir / "purchase_source_records.csv", source_records)
    write_csv(args.out_dir / "purchase_candidates_review.csv", review_rows)
    write_csv(
        args.out_dir / "purchase_candidates_db.csv",
        review_rows,
        fieldnames=[
            "source_system",
            "source_record_id",
            "purchase_number",
            "title",
            "customer_name",
            "customer_inn",
            "publication_date",
            "amount_rub",
            "source_url",
            "match_quality",
        ],
    )
    write_csv(args.out_dir / "purchase_duplicates.csv", duplicate_rows)
    write_csv(args.out_dir / "organizations_clean.csv", organizations)
    write_csv(args.out_dir / "purchase_documents_plan.csv", document_plan)
    (args.out_dir / "duplicate_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "initial_analysis.json").write_text(
        json.dumps(initial_analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
