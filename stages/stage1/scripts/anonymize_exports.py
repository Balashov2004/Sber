from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

try:
    from .anonymize import anonymize_record
except ImportError:
    from anonymize import anonymize_record


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "interim"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "anonymized"


def anonymize_csv(input_path: Path, output_path: Path) -> dict[str, str | int]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = [anonymize_record(row) for row in reader]
        fieldnames = reader.fieldnames or []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "rows": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create anonymized CSV exports from interim data.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--files",
        nargs="*",
        default=[
            "stage1_purchases_strict.csv",
            "stage1_purchases_candidates.csv",
            "eis_broad_purchase_index.csv",
            "eis_broad_purchase_candidates.csv",
            "sberbank_ast_purchase_candidates.csv",
            "sberbank_ast_purchase_index.csv",
            "source_probe_links.csv",
        ],
        help="CSV filenames inside input-dir to anonymize.",
    )
    args = parser.parse_args()

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "files": [],
    }

    for filename in args.files:
        input_path = args.input_dir / filename
        if not input_path.exists():
            report["files"].append({"input": str(input_path), "status": "missing"})
            continue
        output_path = args.output_dir / filename
        result = anonymize_csv(input_path, output_path)
        result["status"] = "ok"
        report["files"].append(result)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "anonymization_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote anonymized files to {args.output_dir}")
    print(f"Wrote report to {report_path}")


if __name__ == "__main__":
    main()
