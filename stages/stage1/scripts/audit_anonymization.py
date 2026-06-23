from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_DIR = PROJECT_ROOT / "data" / "processed" / "anonymized"
REPORT_PATH = INPUT_DIR / "pii_audit_report.json"

PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+7|8)[\s\-.(]*\d{3}[\s\-.)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"),
    "passport_labeled": re.compile(r"(?i)\bпаспорт(?:\s+рф)?[\s:№#-]*\d{2}\s?\d{2}[\s,;/-]*\d{6}\b"),
    "snils": re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b"),
    "personal_inn_labeled": re.compile(r"(?i)\bинн\s*(?:физ(?:ического)?\s*лица)?[\s:№#-]*\d{12}\b"),
}


def main() -> None:
    findings: list[dict[str, object]] = []
    scanned_rows = 0
    scanned_files = 0
    by_type: Counter[str] = Counter()
    for path in sorted(INPUT_DIR.glob("*.csv")):
        scanned_files += 1
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            for line_number, row in enumerate(csv.DictReader(fh), start=2):
                scanned_rows += 1
                for field, value in row.items():
                    if not isinstance(value, str) or not value:
                        continue
                    for finding_type, pattern in PATTERNS.items():
                        if pattern.search(value):
                            by_type[finding_type] += 1
                            if len(findings) < 100:
                                findings.append(
                                    {
                                        "file": path.name,
                                        "line": line_number,
                                        "field": field,
                                        "finding_type": finding_type,
                                        "value_preview": value[:120],
                                    }
                                )

    report = {
        "scanned_files": scanned_files,
        "scanned_rows": scanned_rows,
        "high_risk_findings": sum(by_type.values()),
        "by_type": dict(by_type),
        "status": "passed" if not by_type else "review_required",
        "sample_findings": findings,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if by_type:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
