from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def count_csv(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return max(sum(1 for _ in csv.DictReader(fh)), 0)


def main() -> None:
    paths = {
        "organizations_seed": PROJECT_ROOT / "stages" / "stage1" / "config" / "sber_organizations_seed.csv",
        "egrul_discovered": PROJECT_ROOT / "data" / "interim" / "egrul_organizations_discovered.csv",
        "eis_candidates": PROJECT_ROOT / "data" / "interim" / "eis_purchase_candidates.csv",
        "eis_index": PROJECT_ROOT / "data" / "interim" / "eis_purchase_index.csv",
        "eis_broad_candidates": PROJECT_ROOT / "data" / "interim" / "eis_broad_purchase_candidates.csv",
        "eis_broad_index": PROJECT_ROOT / "data" / "interim" / "eis_broad_purchase_index.csv",
        "sberbank_ast_candidates": PROJECT_ROOT / "data" / "interim" / "sberbank_ast_purchase_candidates.csv",
        "sberbank_ast_index": PROJECT_ROOT / "data" / "interim" / "sberbank_ast_purchase_index.csv",
        "source_probe_results": PROJECT_ROOT / "data" / "interim" / "source_probe_results.csv",
        "source_probe_links": PROJECT_ROOT / "data" / "interim" / "source_probe_links.csv",
        "collection_log": PROJECT_ROOT / "logs" / "collection_log.csv",
        "eis_query_collection_log": PROJECT_ROOT / "logs" / "eis_query_collection_log.csv",
    }

    raw_eis = list((PROJECT_ROOT / "data" / "raw" / "eis" / "search_pages").glob("*.html"))
    raw_ast = list((PROJECT_ROOT / "data" / "raw" / "sberbank_ast").glob("*"))
    raw_inspect = list((PROJECT_ROOT / "data" / "raw" / "html_inspect").glob("*"))
    raw_probes = list((PROJECT_ROOT / "data" / "raw" / "source_probes").glob("*"))

    print("Stage 1 summary")
    print("================")
    for name, path in paths.items():
        print(f"{name}: {count_csv(path)} rows")
    print(f"raw_eis_html_pages: {len(raw_eis)} files")
    print(f"raw_sberbank_ast_files: {len(raw_ast)} files")
    print(f"raw_html_inspect_files: {len(raw_inspect)} files")
    print(f"raw_source_probe_files: {len(raw_probes)} files")
    print("implemented_sources: EIS, FNS EGRUL, Sberbank-AST, source probes for all requested ETPs")
    print("source_registry_entries: 8")


if __name__ == "__main__":
    main()
