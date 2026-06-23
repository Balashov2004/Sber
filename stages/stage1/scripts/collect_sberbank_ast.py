from __future__ import annotations

import argparse
import csv
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "sberbank_ast"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
DEFAULT_ORGS = PROJECT_ROOT / "stages" / "stage1" / "config" / "sber_organizations_seed.csv"
PLATFORM_OPERATOR_INNS = {"7707308480"}
NON_PROCUREMENT_SOURCE_PREFIXES = (
    "Реализация имущества",
    "Продажа имущества",
)
NON_PROCUREMENT_TYPE_MARKERS = (
    "простая продажа",
    "(продажа",
    "продажа,",
)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Referer": "https://utp.sberbank-ast.ru/Main/List/UnitedPurchaseListNew",
}


def fetch_url(url: str) -> str:
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def post_form(url: str, data: dict[str, str]) -> str:
    encoded = urlencode(data).encode("utf-8")
    headers = {
        **HEADERS,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    request = Request(url, data=encoded, headers=headers)
    with urlopen(request, timeout=60) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_settings_xml(page_html: str) -> str:
    match = re.search(r'id="settingsXml"\s+value="(.*?)"', page_html, flags=re.S)
    if not match:
        raise RuntimeError("settingsXml was not found")
    return html.unescape(match.group(1))


def set_xml_value(xml: str, tag: str, value: str) -> str:
    pattern = rf"(<{tag}>\s*<value>)(.*?)(</value>)"
    return re.sub(pattern, rf"\g<1>{html.escape(value)}\g<3>", xml, count=1, flags=re.S)


def set_xml_range(xml: str, tag: str, minvalue: str, maxvalue: str) -> str:
    pattern = rf"(<{tag}>\s*<minvalue>)(.*?)(</minvalue>\s*<maxvalue>)(.*?)(</maxvalue>)"
    return re.sub(pattern, rf"\g<1>{minvalue}\g<3>{maxvalue}\g<5>", xml, count=1, flags=re.S)


SEARCH_FIELDS = [
    "TradeSectionId",
    "purchAmount",
    "purchCurrency",
    "purchCodeTerm",
    "purchCode",
    "PurchaseTypeName",
    "purchStateName",
    "BidStatusName",
    "OrgName",
    "OrgFullName",
    "OrgInn",
    "CustomerFullName",
    "CustomerInn",
    "SourceTerm",
    "PublicDate",
    "RequestDate",
    "RequestStartDate",
    "RequestAcceptDate",
    "EndDate",
    "purchName",
    "BidName",
    "SourceHrefTerm",
    "objectHrefTerm",
    "IsSMP",
    "PurchaseTypeType",
    "PurchaseStageTerm",
    "PurchaseWayTerm",
    "BranchNameTerm",
    "RegionName",
    "productNames",
]


def build_search_xml(filters_xml: str, page: int = 1, page_size: int = 100) -> str:
    """Wrap visible filters in the full XML request expected by UTP search.

    Sending the ``filters`` fragment alone is accepted by the endpoint but the
    filters are ignored, which previously returned arbitrary 2022 SberB2B rows.
    """
    root = ET.fromstring(filters_xml)
    elastic = ET.Element("elasticrequest")
    elastic.append(root)

    fields = ET.SubElement(elastic, "fields")
    for field in SEARCH_FIELDS:
        ET.SubElement(fields, "field").text = field

    sort = ET.SubElement(elastic, "sort")
    ET.SubElement(sort, "value").text = "PublicDate"
    ET.SubElement(sort, "direction").text = "desc"
    ET.SubElement(elastic, "aggregations")
    ET.SubElement(elastic, "size").text = str(page_size)
    ET.SubElement(elastic, "from").text = str(max(page - 1, 0) * page_size)
    return ET.tostring(elastic, encoding="unicode")


def parse_response(response_text: str) -> tuple[dict, str, int]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return {}, response_text, 0
    table_xml = ""
    data = payload.get("Data") or payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        nested_data = data.get("Data") if isinstance(data.get("Data"), dict) else {}
        table_xml = (
            data.get("tableXml")
            or data.get("TableXml")
            or data.get("table")
            or nested_data.get("tableXml")
            or nested_data.get("TableXml")
            or ""
        )
    elif isinstance(data, str):
        table_xml = data
    pager_total = 0
    if isinstance(data, dict):
        nested_data = data.get("Data") if isinstance(data.get("Data"), dict) else {}
        raw_total = data.get("pagerTotal") or nested_data.get("pagerTotal") or 0
        try:
            pager_total = int(raw_total)
        except (TypeError, ValueError):
            pager_total = 0
    return payload, table_xml, pager_total


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_table_xml(table_xml: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        root = ET.fromstring(table_xml)
        source_nodes = root.findall(".//_source")
        if not source_nodes:
            source_nodes = root.findall(".//row")
        for source_node in source_nodes:
            row: dict[str, str] = {}
            for child in list(source_node):
                row[child.tag] = "".join(child.itertext()).strip()
            if row:
                rows.append(row)
        return rows
    except ET.ParseError:
        pass

    blocks = re.findall(r"<_source\b.*?</_source>", table_xml, flags=re.S) or re.findall(r"<row\b.*?</row>", table_xml, flags=re.S)
    for row_xml in blocks:
        row = {}
        for key, value in re.findall(r"<([A-Za-z0-9_]+)>(.*?)</\1>", row_xml, flags=re.S):
            row[key] = strip_tags(value)
        if row:
            rows.append(row)
    return rows


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


def read_sber_inns(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {row.get("inn", "").strip() for row in csv.DictReader(fh) if row.get("inn", "").strip()}


def read_search_terms(path: Path, mode: str = "inn") -> list[str]:
    terms: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if mode == "inn":
                values = (row.get("inn", ""),)
            elif mode == "names":
                values = (row.get("legal_name", ""), row.get("short_name", ""))
            else:
                values = (
                    row.get("inn", ""),
                    row.get("legal_name", ""),
                    row.get("short_name", ""),
                    *(row.get("aliases", "").split("|")),
                )
            for value in values:
                value = value.strip()
                if value and value not in terms:
                    terms.append(value)
    return terms


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        record_id = (
            row.get("PurchaseId")
            or row.get("Bid_id")
            or row.get("purchCode")
            or row.get("BidNo")
            or row.get("objectHrefTerm")
            or ""
        )
        unique[(row.get("SourceTerm", ""), record_id)] = row
    return list(unique.values())


def parse_ru_datetime(value: str) -> datetime | None:
    value = (value or "").strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def filter_sber_rows(
    rows: list[dict[str, str]],
    sber_inns: set[str],
    from_year: int = 2024,
    to_year: int = 2025,
    include_non_procurement: bool = False,
) -> list[dict[str, str]]:
    filtered = []
    for row in rows:
        customer_inn = row.get("CustomerInn", "")
        organizer_inn = row.get("OrgInn", "")
        customer_match = customer_inn in sber_inns
        organizer_match = (
            not customer_inn
            and organizer_inn in sber_inns
            and organizer_inn not in PLATFORM_OPERATOR_INNS
        )
        inn_match = customer_match or organizer_match
        dt = parse_ru_datetime(row.get("PublicDate") or row.get("PublicDateText") or row.get("RequestStartDate"))
        date_match = dt is not None and from_year <= dt.year <= to_year
        source_term = row.get("SourceTerm", "")
        purchase_type = " ".join(
            (
                row.get("PurchaseTypeName", ""),
                row.get("PurchaseWayTerm", ""),
            )
        ).lower()
        procurement_match = include_non_procurement or (
            not source_term.startswith(NON_PROCUREMENT_SOURCE_PREFIXES)
            and not any(marker in purchase_type for marker in NON_PROCUREMENT_TYPE_MARKERS)
        )
        row["is_sber_group_match"] = "1" if inn_match else "0"
        row["is_target_period"] = "1" if date_match else "0"
        row["is_procurement_scope"] = "1" if procurement_match else "0"
        if inn_match and date_match and procurement_match:
            filtered.append(row)
    return filtered


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect public Sberbank-AST unified purchase list records.")
    parser.add_argument("--query", default="Сбербанк")
    parser.add_argument("--from-date", default="01.01.2024 00:00")
    parser.add_argument("--to-date", default="31.12.2025 23:59")
    parser.add_argument("--all-orgs", action="store_true", help="Search every verified INN and organization alias.")
    parser.add_argument("--term-mode", choices=("inn", "names", "all"), default="inn")
    parser.add_argument("--include-non-procurement", action="store_true")
    parser.add_argument(
        "--rebuild-index-only",
        action="store_true",
        help="Reapply Sber and procurement-scope filters to the cached candidates file.",
    )
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--page-size", type=int, default=100)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)

    if args.rebuild_index_only:
        cached_path = INTERIM_DIR / "sberbank_ast_purchase_candidates.csv"
        with cached_path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        sber_index = filter_sber_rows(
            rows,
            read_sber_inns(DEFAULT_ORGS),
            include_non_procurement=args.include_non_procurement,
        )
        index_rows_written = write_csv(INTERIM_DIR / "sberbank_ast_purchase_index.csv", sber_index)
        print(f"Rebuilt {index_rows_written} rows in {INTERIM_DIR / 'sberbank_ast_purchase_index.csv'}")
        return

    list_url = "https://utp.sberbank-ast.ru/Main/List/UnitedPurchaseListNew"
    page_html = fetch_url(list_url)
    (RAW_DIR / "united_purchase_list_page.html").write_text(page_html, encoding="utf-8")

    base_filters = extract_settings_xml(page_html)
    search_terms = read_search_terms(DEFAULT_ORGS, args.term_mode) if args.all_orgs else [args.query]
    rows: list[dict[str, str]] = []
    last_payload: dict = {}
    for term_index, term in enumerate(search_terms, start=1):
        for page in range(1, args.pages + 1):
            filters = set_xml_value(base_filters, "mainSearchBar", term)
            filters = set_xml_range(filters, "PublicDate", args.from_date, args.to_date)
            xml = build_search_xml(filters, page=page, page_size=args.page_size)
            request_path = RAW_DIR / f"request_{term_index:03d}_page_{page:03d}.xml"
            request_path.write_text(xml, encoding="utf-8")

            response_text = post_form(
                "https://utp.sberbank-ast.ru/Main/SearchQuery/UnitedPurchaseListNew",
                {
                    "xmlData": xml,
                    "orgId": "0",
                    "buId": "0",
                    "personId": "0",
                    "buMainId": "0",
                    "personMainId": "0",
                },
            )
            response_path = RAW_DIR / f"response_{term_index:03d}_page_{page:03d}.json"
            response_path.write_text(response_text, encoding="utf-8")
            payload, table_xml, pager_total = parse_response(response_text)
            last_payload = payload
            page_rows = parse_table_xml(table_xml or response_text)
            for row in page_rows:
                row["search_term"] = term
                row["search_page"] = str(page)
            rows.extend(page_rows)
            print(f"{term!r}, page {page}: {len(page_rows)} rows, total={pager_total}")
            if not page_rows or page * args.page_size >= pager_total:
                break

    rows = dedupe_rows(rows)
    sber_index = filter_sber_rows(
        rows,
        read_sber_inns(DEFAULT_ORGS),
        include_non_procurement=args.include_non_procurement,
    )
    rows_written = write_csv(INTERIM_DIR / "sberbank_ast_purchase_candidates.csv", rows)
    index_rows_written = write_csv(INTERIM_DIR / "sberbank_ast_purchase_index.csv", sber_index)

    print(f"Response JSON keys: {list(last_payload.keys()) if last_payload else 'non-json'}")
    print(f"Wrote {rows_written} records to {INTERIM_DIR / 'sberbank_ast_purchase_candidates.csv'}")
    print(f"Wrote {index_rows_written} records to {INTERIM_DIR / 'sberbank_ast_purchase_index.csv'}")


if __name__ == "__main__":
    main()
