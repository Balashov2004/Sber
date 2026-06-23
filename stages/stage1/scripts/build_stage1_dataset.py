from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return 0
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def procurement_key(row: dict[str, str]) -> tuple[str, str]:
    record_id = next(
        (
            row.get(field, "").strip()
            for field in ("purchase_number", "PurchaseId", "Bid_id", "purchCode", "BidNo", "objectHrefTerm")
            if row.get(field, "").strip()
        ),
        "",
    )
    if record_id:
        return row.get("source_system", ""), record_id
    return row.get("source_system", ""), repr(sorted(row.items()))


def tag_rows(rows: list[dict[str, str]], source: str, layer: str) -> list[dict[str, str]]:
    tagged = []
    for row in rows:
        copy = dict(row)
        copy["source_system"] = source
        copy["data_layer"] = layer
        tagged.append(copy)
    return tagged


def main() -> None:
    eis_strict = tag_rows(read_csv(INTERIM_DIR / "eis_purchase_index.csv"), "EIS", "strict")
    eis_broad_strict = tag_rows(read_csv(INTERIM_DIR / "eis_broad_purchase_index.csv"), "EIS", "strict_broad")
    eis_candidates = tag_rows(read_csv(INTERIM_DIR / "eis_broad_purchase_candidates.csv"), "EIS", "candidate")
    ast_candidates = tag_rows(read_csv(INTERIM_DIR / "sberbank_ast_purchase_candidates.csv"), "Sberbank-AST", "candidate")
    ast_strict = tag_rows(read_csv(INTERIM_DIR / "sberbank_ast_purchase_index.csv"), "Sberbank-AST", "strict")

    strict = list({procurement_key(row): row for row in eis_strict + eis_broad_strict + ast_strict}.values())
    candidates = list({procurement_key(row): row for row in eis_candidates + ast_candidates}.values())

    strict_count = write_csv(INTERIM_DIR / "stage1_purchases_strict.csv", strict)
    candidate_count = write_csv(INTERIM_DIR / "stage1_purchases_candidates.csv", candidates)
    print(f"Wrote {strict_count} strict rows to {INTERIM_DIR / 'stage1_purchases_strict.csv'}")
    print(f"Wrote {candidate_count} candidate rows to {INTERIM_DIR / 'stage1_purchases_candidates.csv'}")


if __name__ == "__main__":
    main()

