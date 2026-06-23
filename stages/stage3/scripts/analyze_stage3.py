from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "stage2" / "purchases_clean.csv"
DEFAULT_EXTERNAL = PROJECT_ROOT / "data" / "external" / "cbr"
DEFAULT_OUT = PROJECT_ROOT / "data" / "processed" / "stage3"

CATEGORY_RULES = [
    (
        "it_and_telecom",
        (
            "программ",
            "лиценз",
            "сервер",
            "информационн",
            "сетев",
            "компьютер",
            "ноутбук",
            "аппаратн",
            "цифров",
            "услуг связи",
            "интернет",
            "видеоконференц",
            "телефони",
            "коммутатор",
            "смартфон",
            "кибер",
            "безопасност",
            "pentest",
        ),
    ),
    (
        "construction_and_repair",
        ("строител", "ремонт", "реконструк", "проектирован", "монтаж", "отделочн"),
    ),
    ("audit_and_assurance", ("аудит", "аудитор", "финансовой отчетности")),
    ("insurance", ("страхован", "осаго", "каско")),
    (
        "professional_services",
        ("консалт", "обучен", "образован", "исследован", "оценк", "юридическ", "маркетинг"),
    ),
    ("logistics_and_facilities", ("перевоз", "достав", "уборк", "клининг", "охран", "питани")),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_iso_date(value: str | None) -> date | None:
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_float(value: object) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_category(text: str) -> tuple[str, float]:
    lowered = (text or "").lower()
    best_category = "other"
    best_hits = 0
    for category, keywords in CATEGORY_RULES:
        hits = sum(keyword in lowered for keyword in keywords)
        if hits > best_hits:
            best_category = category
            best_hits = hits
    if not best_hits:
        return "other", 0.35
    return best_category, min(0.55 + 0.08 * best_hits, 0.95)


def derive_status(text: str, current: str) -> str:
    lowered = f"{text} {current}".lower()
    if "отмен" in lowered:
        return "cancelled"
    if any(token in lowered for token in ("заверш", "подведен", "подведён", "определен", "определён")):
        return "completed"
    if "подача заявок" in lowered:
        return "applications"
    return current or "unknown"


def normalize_subject(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"№\s*\d+", " ", lowered)
    lowered = re.sub(r"\b\d{6,}\b", " ", lowered)
    lowered = re.sub(
        r"определение поставщика (?:завершено|отменено)|закупка (?:завершена|отменена)",
        " ",
        lowered,
    )
    return re.sub(r"[^а-яёa-z0-9]+", " ", lowered).strip()[:240]


def enrich(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        item: dict[str, object] = dict(row)
        category, confidence = classify_category(row.get("title", ""))
        publication = parse_iso_date(row.get("publication_date"))
        amount = parse_float(row.get("amount_rub"))
        item["category"] = category
        item["category_confidence"] = confidence
        item["derived_status"] = derive_status(row.get("title", ""), row.get("status", ""))
        item["subject_normalized"] = normalize_subject(row.get("title", ""))
        item["amount_rub"] = amount
        item["year"] = publication.year if publication else ""
        item["month"] = publication.strftime("%Y-%m") if publication else ""
        output.append(item)
    return output


def aggregate_annual(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for year in (2024, 2025):
        group = [row for row in rows if row.get("year") == year]
        amounts = [float(row["amount_rub"]) for row in group if row.get("amount_rub") is not None]
        result.append(
            {
                "year": year,
                "purchase_count": len(group),
                "amount_present": len(amounts),
                "amount_coverage_pct": round(100 * len(amounts) / len(group), 2) if group else 0,
                "total_amount_rub": round(sum(amounts), 2),
                "median_amount_rub": round(statistics.median(amounts), 2) if amounts else "",
            }
        )
    return result


def aggregate_categories(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    categories = sorted({str(row["category"]) for row in rows})
    for category in categories:
        yearly = {}
        for year in (2024, 2025):
            group = [row for row in rows if row.get("category") == category and row.get("year") == year]
            amounts = [float(row["amount_rub"]) for row in group if row.get("amount_rub") is not None]
            yearly[year] = {"count": len(group), "amount": sum(amounts)}
        count_2024 = yearly[2024]["count"]
        amount_2024 = yearly[2024]["amount"]
        result.append(
            {
                "category": category,
                "count_2024": count_2024,
                "count_2025": yearly[2025]["count"],
                "count_change_pct": round(100 * (yearly[2025]["count"] - count_2024) / count_2024, 2)
                if count_2024
                else "",
                "amount_2024_rub": round(amount_2024, 2),
                "amount_2025_rub": round(yearly[2025]["amount"], 2),
                "amount_change_pct": round(100 * (yearly[2025]["amount"] - amount_2024) / amount_2024, 2)
                if amount_2024
                else "",
            }
        )
    return sorted(result, key=lambda row: int(row["count_2025"]) + int(row["count_2024"]), reverse=True)


def aggregate_monthly(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    months = [f"{year}-{month:02d}" for year in (2024, 2025) for month in range(1, 13)]
    for month in months:
        group = [row for row in rows if row.get("month") == month]
        it_group = [row for row in group if row.get("category") == "it_and_telecom"]
        construction = [row for row in group if row.get("category") == "construction_and_repair"]
        result.append(
            {
                "month": month,
                "purchase_count": len(group),
                "total_amount_rub": round(sum(float(row["amount_rub"]) for row in group if row.get("amount_rub") is not None), 2),
                "it_count": len(it_group),
                "it_amount_rub": round(sum(float(row["amount_rub"]) for row in it_group if row.get("amount_rub") is not None), 2),
                "construction_count": len(construction),
                "construction_amount_rub": round(
                    sum(float(row["amount_rub"]) for row in construction if row.get("amount_rub") is not None), 2
                ),
            }
        )
    return result


def monthly_external(path: Path, value_field: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in read_csv(path):
        parsed = parse_iso_date(row.get("date"))
        value = parse_float(row.get(value_field))
        if parsed and value is not None:
            grouped[parsed.strftime("%Y-%m")].append(value)
    return {month: statistics.mean(values) for month, values in grouped.items()}


def join_external(monthly: list[dict[str, object]], external_dir: Path) -> list[dict[str, object]]:
    usd = monthly_external(external_dir / "usd_rub_daily.csv", "usd_rub")
    rate = monthly_external(external_dir / "key_rate_daily.csv", "key_rate")
    output = []
    for row in monthly:
        item = dict(row)
        item["usd_rub_avg"] = round(usd[str(row["month"])], 4) if str(row["month"]) in usd else ""
        item["key_rate_avg"] = round(rate[str(row["month"])], 4) if str(row["month"]) in rate else ""
        output.append(item)
    return output


def pearson_with_p(xs: list[float], ys: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 3 or len(xs) != len(ys):
        return None, None
    def coefficient(left: list[float], right: list[float]) -> float | None:
        mean_x, mean_y = statistics.mean(left), statistics.mean(right)
        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(left, right))
        denominator = math.sqrt(
            sum((x - mean_x) ** 2 for x in left) * sum((y - mean_y) ** 2 for y in right)
        )
        return numerator / denominator if denominator else None

    observed = coefficient(xs, ys)
    if observed is None:
        return None, None
    randomizer = random.Random(42)
    shuffled = list(ys)
    extreme = 0
    iterations = 10000
    for _ in range(iterations):
        randomizer.shuffle(shuffled)
        candidate = coefficient(xs, shuffled)
        if candidate is not None and abs(candidate) >= abs(observed):
            extreme += 1
    return observed, (extreme + 1) / (iterations + 1)


def build_hypotheses(monthly: list[dict[str, object]]) -> list[dict[str, object]]:
    definitions = [
        ("IT procurement amount vs USD/RUB", "it_amount_rub", "usd_rub_avg"),
        ("IT procurement count vs USD/RUB", "it_count", "usd_rub_avg"),
        ("Construction procurement amount vs key rate", "construction_amount_rub", "key_rate_avg"),
        ("Construction procurement count vs key rate", "construction_count", "key_rate_avg"),
    ]
    result = []
    for name, metric, factor in definitions:
        pairs = [
            (math.log1p(float(row[metric])) if "amount" in metric else float(row[metric]), float(row[factor]))
            for row in monthly
            if row.get(factor) not in ("", None)
        ]
        coefficient, p_value = pearson_with_p([x for x, _ in pairs], [y for _, y in pairs])
        significant = p_value is not None and p_value < 0.05
        result.append(
            {
                "hypothesis": name,
                "metric": metric,
                "factor": factor,
                "observations": len(pairs),
                "transformation": "log1p" if "amount" in metric else "none",
                "pearson_r": round(coefficient, 4) if coefficient is not None else None,
                "p_value": round(p_value, 4) if p_value is not None else None,
                "decision": "statistically_significant_association" if significant else "not_statistically_significant",
                "limitation": "Monthly observational association does not establish causality; category classification is keyword-based.",
            }
        )
    return result


def detect_anomalies(
    rows: list[dict[str, object]], annual: list[dict[str, object]] | None = None
) -> list[dict[str, object]]:
    anomalies = []
    amounts = [float(row["amount_rub"]) for row in rows if row.get("amount_rub") is not None]
    if amounts:
        median = statistics.median(amounts)
        deviations = [abs(value - median) for value in amounts]
        mad = statistics.median(deviations)
        threshold = sorted(amounts)[max(0, math.ceil(len(amounts) * 0.99) - 1)]
        for row in rows:
            amount = parse_float(row.get("amount_rub"))
            if amount is None:
                continue
            robust_z = 0.6745 * (amount - median) / mad if mad else 0
            if robust_z > 25 and amount >= threshold:
                anomalies.append(
                    {
                        "anomaly_type": "extreme_amount",
                        "severity": "high",
                        "purchase_number": row.get("purchase_number", ""),
                        "category": row.get("category", ""),
                        "metric": round(robust_z, 2),
                        "amount_rub": round(amount, 2),
                        "description": "Amount is an extreme robust-MAD outlier.",
                    }
                )
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        customer_key = str(row.get("customer_inn") or row.get("customer_name") or "")
        key = (customer_key, str(row.get("subject_normalized", "")))
        if key[0] and key[1]:
            groups[key].append(row)
        if row.get("derived_status") == "cancelled":
            anomalies.append(
                {
                    "anomaly_type": "cancelled_procedure",
                    "severity": "medium",
                    "purchase_number": row.get("purchase_number", ""),
                    "category": row.get("category", ""),
                    "metric": "",
                    "amount_rub": row.get("amount_rub", ""),
                    "description": "Procedure status contains a cancellation signal.",
                }
            )
            if "подача" in str(row.get("status", "")).lower():
                anomalies.append(
                    {
                        "anomaly_type": "status_field_conflict",
                        "severity": "medium",
                        "purchase_number": row.get("purchase_number", ""),
                        "category": row.get("category", ""),
                        "metric": "",
                        "amount_rub": row.get("amount_rub", ""),
                        "description": "Structured status conflicts with the cancellation signal.",
                    }
                )
    for group in groups.values():
        if len(group) < 2:
            continue
        sorted_group = sorted(group, key=lambda row: str(row.get("publication_date", "")))
        for left, right in zip(sorted_group, sorted_group[1:]):
            left_amount = parse_float(left.get("amount_rub"))
            right_amount = parse_float(right.get("amount_rub"))
            if left_amount is None or right_amount is None or min(left_amount, right_amount) <= 0:
                continue
            ratio = max(left_amount, right_amount) / min(left_amount, right_amount)
            if ratio >= 2:
                anomalies.append(
                    {
                        "anomaly_type": "same_subject_price_jump",
                        "severity": "high",
                        "purchase_number": f"{left.get('purchase_number')} -> {right.get('purchase_number')}",
                        "category": left.get("category", ""),
                        "metric": round(ratio, 2),
                        "amount_rub": right_amount,
                        "description": "Similar subject for the same customer changed in price by at least two times.",
                    }
                )
            statuses = {left.get("derived_status"), right.get("derived_status")}
            if statuses == {"cancelled", "completed"}:
                anomalies.append(
                    {
                        "anomaly_type": "cancelled_then_republished",
                        "severity": "medium",
                        "purchase_number": f"{left.get('purchase_number')} -> {right.get('purchase_number')}",
                        "category": left.get("category", ""),
                        "metric": "",
                        "amount_rub": right_amount,
                        "description": "Similar procedure appears as cancelled and completed.",
                    }
                )
    if annual:
        missing_years = [
            row.get("year")
            for row in annual
            if row.get("coverage_status") == "missing_verified_data" or row.get("purchase_count") == 0
        ]
        if missing_years:
            anomalies.append(
                {
                    "anomaly_type": "coverage_gap",
                    "severity": "critical",
                    "purchase_number": "",
                    "category": "",
                    "metric": ",".join(str(year) for year in missing_years),
                    "amount_rub": "",
                    "description": "One or more target years have no verified records.",
                }
            )
    return anomalies


def build_llm_tasks(rows: list[dict[str, object]], anomalies: list[dict[str, object]]) -> list[dict[str, object]]:
    flags: dict[str, list[str]] = defaultdict(list)
    for anomaly in anomalies:
        for number in str(anomaly.get("purchase_number", "")).split(" -> "):
            flags[number].append(str(anomaly["anomaly_type"]))
    tasks = []
    for row in rows:
        number = str(row.get("purchase_number", ""))
        if row.get("category") != "it_and_telecom" and number not in flags:
            continue
        tasks.append(
            {
                "task_id": f"purchase-{number}",
                "task": "procurement_notice_review",
                "input": {
                    "purchase_number": number,
                    "customer": row.get("customer_name", ""),
                    "date": row.get("publication_date", ""),
                    "amount_rub": row.get("amount_rub"),
                    "title": row.get("title", ""),
                    "rule_category": row.get("category", ""),
                    "anomaly_flags": flags.get(number, []),
                },
                "expected_output": {
                    "category": "string",
                    "category_confidence": "number",
                    "single_supplier_signal": "boolean|null",
                    "price_or_scope_risk": "string|null",
                    "observation": "string",
                    "interpretation": "string",
                    "significance": "string",
                    "limitation": "string",
                },
            }
        )
    return tasks


def build_summary(
    rows: list[dict[str, object]],
    annual: list[dict[str, object]],
    categories: list[dict[str, object]],
    hypotheses: list[dict[str, object]],
    anomalies: list[dict[str, object]],
) -> dict[str, object]:
    it_rows = [row for row in rows if row.get("category") == "it_and_telecom"]
    it_amount = sum(float(row["amount_rub"]) for row in it_rows if row.get("amount_rub") is not None)
    anomaly_counts = Counter(str(row["anomaly_type"]) for row in anomalies)
    return {
        "selected_direction": "it_and_telecom",
        "selection_reason": {
            "purchase_count": len(it_rows),
            "amount_rub": round(it_amount, 2),
            "share_of_all_purchases_pct": round(100 * len(it_rows) / len(rows), 2) if rows else 0,
            "rationale": "The direction is large, economically material and plausibly exposed to imported hardware, software licences and USD/RUB.",
        },
        "annual_comparison": annual,
        "category_comparison": categories,
        "hypotheses": hypotheses,
        "anomaly_counts": dict(anomaly_counts),
        "supplier_analysis_status": "blocked_until_participant_and_winner_protocols_are_extracted",
        "llm_role": "classification validation, unstructured notice review, anomaly explanation and four-part conclusion drafting",
    }


def build_markdown(summary: dict[str, object]) -> str:
    annual = summary["annual_comparison"]
    direction = summary["selection_reason"]
    hypotheses = summary["hypotheses"]
    return f"""# Этап 3. Аналитический модуль

## Выбранное направление

IT и телеком: {direction['purchase_count']} закупок, {direction['amount_rub']:,.2f} руб., {direction['share_of_all_purchases_pct']}% подтверждённой выборки по количеству.

Наблюдение: направление крупное и включает программное обеспечение, лицензии, аппаратные и телеком-решения.
Интерпретация: часть стоимости может зависеть от импортных компонентов и валютного курса.
Значимость: направление достаточно представительно для динамического и корреляционного анализа.
Ограничение: классификация основана на ключевых словах и требует проверки документов для неоднозначных предметов.

## Сравнение 2024 и 2025

2024: {annual[0]['purchase_count']} закупок на {annual[0]['total_amount_rub']:,.2f} руб.
2025: {annual[1]['purchase_count']} закупок на {annual[1]['total_amount_rub']:,.2f} руб.

Наблюдение: количество подтверждённых закупок в 2025 году выше, чем в 2024 году.
Интерпретация: рост отражает одновременно закупочную активность и улучшившееся покрытие источника; его нельзя целиком считать бизнес-ростом.
Значимость: сравнение показывает изменение структуры и нагрузки по годам.
Ограничение: данные не содержат полной суммы заключённых контрактов, а часть НМЦ отсутствует или указана как тариф/единичная цена.

## Корреляции

{json.dumps(hypotheses, ensure_ascii=False, indent=2)}

Наблюдение: коэффициенты рассчитаны по 24 месячным наблюдениям с p-value.
Интерпретация: статистическая связь принимается только при p < 0,05.
Значимость: проверка отделяет визуальное совпадение динамики от статистически подтверждаемой ассоциации.
Ограничение: корреляция не доказывает причинность; возможны сезонность, лаг закупочного цикла и влияние нескольких факторов.

## Аномалии

{json.dumps(summary['anomaly_counts'], ensure_ascii=False, indent=2)}

Наблюдение: сформированы списки экстремальных сумм, отмен, повторных публикаций и скачков цены похожего предмета.
Интерпретация: сигнал является поводом открыть карточку и документы, а не доказательством нарушения.
Значимость: список задаёт приоритет ручной проверки.
Ограничение: единственного участника и долю побед поставщиков пока нельзя проверить без протоколов участников и победителей.

## LLM

LLM-задачи подготовлены для IT-закупок и аномальных карточек. Модель должна проверять категорию, извлекать признаки единственного поставщика, объяснять риск и формировать вывод в формате наблюдение, интерпретация, значимость, ограничение. Отсутствующие факты запрещено додумывать.
"""


def build_charts(
    monthly: list[dict[str, object]],
    categories: list[dict[str, object]],
    rows: list[dict[str, object]],
    out_dir: Path,
) -> None:
    charts = out_dir / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    def save_svg(path: Path, width: int, height: int, body: str) -> None:
        path.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<rect width="100%" height="100%" fill="white"/>{body}</svg>',
            encoding="utf-8",
        )

    def polyline(values: list[float], color: str, width: int, height: int, margin: int) -> str:
        maximum = max(values) or 1
        points = []
        for index, value in enumerate(values):
            x = margin + index * (width - 2 * margin) / max(1, len(values) - 1)
            y = height - margin - value * (height - 2 * margin) / maximum
            points.append(f"{x:.1f},{y:.1f}")
        return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>'

    months = [str(row["month"]) for row in monthly]
    counts = [int(row["purchase_count"]) for row in monthly]
    it_counts = [int(row["it_count"]) for row in monthly]
    width, height, margin = 1200, 520, 70
    labels = "".join(
        f'<text x="{margin + i * (width - 2 * margin) / 23:.1f}" y="485" font-size="12" '
        f'text-anchor="end" transform="rotate(-55 {margin + i * (width - 2 * margin) / 23:.1f} 485)">{month}</text>'
        for i, month in enumerate(months)
    )
    body = (
        '<text x="70" y="30" font-size="22">Динамика закупок по месяцам</text>'
        '<text x="900" y="30" fill="#2563eb">Все закупки</text>'
        '<text x="1040" y="30" fill="#16a34a">IT и телеком</text>'
        + polyline(counts, "#2563eb", width, height, margin)
        + polyline(it_counts, "#16a34a", width, height, margin)
        + labels
    )
    save_svg(charts / "monthly_dynamics.svg", width, height, body)

    top_categories = categories[:6]
    category_labels = [str(row["category"]) for row in top_categories]
    values_2024 = [int(row["count_2024"]) for row in top_categories]
    values_2025 = [int(row["count_2025"]) for row in top_categories]
    maximum = max(values_2024 + values_2025) or 1
    bars = []
    for index, label in enumerate(category_labels):
        x = 80 + index * 170
        height_2024 = values_2024[index] / maximum * 350
        height_2025 = values_2025[index] / maximum * 350
        bars.extend(
            [
                f'<rect x="{x}" y="{430-height_2024:.1f}" width="55" height="{height_2024:.1f}" fill="#2563eb"/>',
                f'<rect x="{x+60}" y="{430-height_2025:.1f}" width="55" height="{height_2025:.1f}" fill="#16a34a"/>',
                f'<text x="{x+55}" y="455" font-size="12" text-anchor="middle">{label}</text>',
            ]
        )
    save_svg(
        charts / "category_comparison.svg",
        1150,
        500,
        '<text x="70" y="30" font-size="22">Структура направлений: 2024 и 2025</text>'
        '<text x="850" y="30" fill="#2563eb">2024</text><text x="930" y="30" fill="#16a34a">2025</text>'
        + "".join(bars),
    )

    expensive = sorted(
        [row for row in rows if row.get("amount_rub") is not None],
        key=lambda row: float(row["amount_rub"]),
        reverse=True,
    )[:20]
    maximum_amount = max(float(row["amount_rub"]) for row in expensive) if expensive else 1
    amount_bars = []
    for index, row in enumerate(expensive):
        y = 55 + index * 28
        bar_width = float(row["amount_rub"]) / maximum_amount * 650
        amount_bars.append(
            f'<text x="10" y="{y+14}" font-size="12">{row.get("purchase_number", "")}</text>'
            f'<rect x="210" y="{y}" width="{bar_width:.1f}" height="18" fill="#7c3aed"/>'
            f'<text x="{220+bar_width:.1f}" y="{y+14}" font-size="12">{float(row["amount_rub"])/1_000_000:.1f}</text>'
        )
    save_svg(
        charts / "top20_amounts.svg",
        1050,
        650,
        '<text x="10" y="28" font-size="22">Топ-20 закупок по указанной сумме, млн руб.</text>'
        + "".join(amount_bars),
    )

    it_amounts = [math.log1p(float(row["it_amount_rub"])) for row in monthly]
    usd = [float(row["usd_rub_avg"]) for row in monthly]
    min_x, max_x = min(usd), max(usd)
    min_y, max_y = min(it_amounts), max(it_amounts)
    dots = []
    for x_value, y_value in zip(usd, it_amounts):
        x = 70 + (x_value - min_x) / (max_x - min_x or 1) * 600
        y = 430 - (y_value - min_y) / (max_y - min_y or 1) * 340
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#dc2626" opacity="0.75"/>')
    save_svg(
        charts / "it_vs_usd.svg",
        760,
        500,
        '<text x="70" y="30" font-size="22">IT-закупки и USD/RUB</text>'
        '<text x="280" y="480" font-size="14">Средний USD/RUB</text>'
        '<text x="15" y="260" font-size="14" transform="rotate(-90 15 260)">log(1 + сумма IT)</text>'
        + "".join(dots),
    )


def build_notebook(out_dir: Path, notebook_path: Path) -> None:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Этап 3. Аналитический модуль\n",
                "Актуальный отчёт построен на подтверждённых закупках Stage 2. Ключевое направление — IT и телеком.",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json\n",
                "from pathlib import Path\n",
                "root = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n",
                "out = root / 'data' / 'processed' / 'stage3'\n",
                "summary = json.loads((out / 'analysis_summary.json').read_text(encoding='utf-8'))\n",
                "summary\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Динамика по месяцам\n",
                "![Динамика](../data/processed/stage3/charts/monthly_dynamics.svg)\n",
                "**Наблюдение:** активность в 2025 году заметно выше, особенно во второй половине года.  \n",
                "**Интерпретация:** возможны сезонность закупочного цикла и расширение покрытия источника.  \n",
                "**Значимость:** месяцы-пики требуют анализа структуры и крупных лотов.  \n",
                "**Ограничение:** динамика публикаций не равна динамике фактического исполнения контрактов.\n",
                "## Структура направлений\n",
                "![Категории](../data/processed/stage3/charts/category_comparison.svg)\n",
                "**Наблюдение:** IT и телеком — крупнейшее содержательное направление; категория other также велика.  \n",
                "**Интерпретация:** короткие и универсальные названия ограничивают словарную классификацию.  \n",
                "**Значимость:** IT достаточно представительно для отдельного исследования.  \n",
                "**Ограничение:** категории требуют проверки спецификаций и документов.\n",
                "## Самые дорогие закупки\n",
                "![Топ закупок](../data/processed/stage3/charts/top20_amounts.svg)\n",
                "**Наблюдение:** небольшое число процедур формирует существенную часть общей суммы.  \n",
                "**Интерпретация:** агрегаты чувствительны к единичным крупным лотам.  \n",
                "**Значимость:** выводы по суммам нужно проверять с медианой и без крупнейших наблюдений.  \n",
                "**Ограничение:** указанная сумма может быть НМЦ, тарифом или единичной расценкой.\n",
                "## IT-закупки и USD/RUB\n",
                "![Корреляция](../data/processed/stage3/charts/it_vs_usd.svg)\n",
                "**Наблюдение:** для суммы IT-закупок статистически значимая линейная связь не обнаружена.  \n",
                "**Интерпретация:** закупочный цикл, лаг планирования и структура лотов сильнее простой синхронной связи.  \n",
                "**Значимость:** визуального сходства недостаточно для подтверждения гипотезы.  \n",
                "**Ограничение:** анализ содержит 24 месяца и не контролирует сезонность и лаги.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": 2,
            "metadata": {},
            "outputs": [],
            "source": [
                "import csv\n",
                "with (out / 'category_comparison.csv').open(encoding='utf-8-sig') as fh:\n",
                "    category_comparison = list(csv.DictReader(fh))\n",
                "category_comparison\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Ограничения\n",
                "Данные об участниках, победителях и итоговой цене требуют извлечения протоколов. Поэтому сигналы единственного участника и концентрации побед поставщиков не объявляются установленными фактами.",
            ],
        },
    ]
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")


def build_html(summary_markdown: str, out_dir: Path) -> None:
    import html

    sections = []
    for line in summary_markdown.splitlines():
        if line.startswith("# "):
            sections.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            sections.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line:
            sections.append(f"<p>{html.escape(line)}</p>")
    images = "".join(
        f'<h2>{title}</h2><img src="charts/{name}" style="max-width:100%;border:1px solid #ddd">'
        for title, name in (
            ("Динамика", "monthly_dynamics.svg"),
            ("Категории", "category_comparison.svg"),
            ("Топ-20", "top20_amounts.svg"),
            ("IT и USD/RUB", "it_vs_usd.svg"),
        )
    )
    document = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Stage 3</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:40px auto;line-height:1.5}"
        "pre,p{white-space:pre-wrap}h1,h2{color:#173b57}</style></head><body>"
        + "".join(sections)
        + images
        + "</body></html>"
    )
    (out_dir / "stage3_analytical_report.html").write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Stage 3 analytical outputs.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = enrich(read_csv(args.input))
    annual = aggregate_annual(rows)
    categories = aggregate_categories(rows)
    monthly = join_external(aggregate_monthly(rows), args.external_dir)
    hypotheses = build_hypotheses(monthly)
    anomalies = detect_anomalies(rows, annual)
    llm_tasks = build_llm_tasks(rows, anomalies)
    summary = build_summary(rows, annual, categories, hypotheses, anomalies)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "purchases_enriched.csv", rows)
    write_csv(args.out_dir / "annual_comparison.csv", annual)
    write_csv(args.out_dir / "category_comparison.csv", categories)
    write_csv(args.out_dir / "monthly_external_analysis.csv", monthly)
    write_csv(args.out_dir / "anomalies.csv", anomalies)
    (args.out_dir / "hypotheses.json").write_text(
        json.dumps(hypotheses, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.out_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary_markdown = build_markdown(summary)
    (args.out_dir / "analysis_summary.md").write_text(summary_markdown, encoding="utf-8")
    with (args.out_dir / "llm_tasks.jsonl").open("w", encoding="utf-8") as fh:
        for task in llm_tasks:
            fh.write(json.dumps(task, ensure_ascii=False) + "\n")
    build_charts(monthly, categories, rows, args.out_dir)
    build_html(summary_markdown, args.out_dir)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "it_rows": summary["selection_reason"]["purchase_count"],
                "annual_rows": len(annual),
                "monthly_rows": len(monthly),
                "anomalies": len(anomalies),
                "llm_tasks": len(llm_tasks),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
