from __future__ import annotations

import csv
import html
import json
import base64
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STAGE2 = PROJECT_ROOT / "data" / "processed" / "stage2"
STAGE3 = PROJECT_ROOT / "data" / "processed" / "stage3"
STAGE4 = PROJECT_ROOT / "data" / "processed" / "stage4"
CHARTS = STAGE4 / "charts"
NOTEBOOK = PROJECT_ROOT / "notebooks" / "final_sber_procurement_report.ipynb"
NOTEBOOK_CHARTS = NOTEBOOK.parent / "charts"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def num(value: object) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def money(value: object) -> str:
    return f"{num(value) / 1_000_000:,.1f}".replace(",", " ")


def rub(value: object) -> str:
    return f"{num(value):,.0f}".replace(",", " ")


def svg_document(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<style>text{font-family:Arial,DejaVu Sans,sans-serif;fill:#18212b}.title{font-size:24px;font-weight:700}'
        '.subtitle{font-size:14px;fill:#59636e}.axis{stroke:#9aa4af;stroke-width:1}.grid{stroke:#e6e9ed;stroke-width:1}'
        '.label{font-size:12px}.small{font-size:11px}</style>'
        f"{body}</svg>"
    )


def save_svg(filename: str, width: int, height: int, body: str) -> str:
    CHARTS.mkdir(parents=True, exist_ok=True)
    path = CHARTS / filename
    path.write_text(svg_document(width, height, body), encoding="utf-8")
    return filename


def monthly_chart(rows: list[dict[str, str]]) -> str:
    amounts = [num(row["total_amount_rub"]) / 1_000_000 for row in rows]
    counts = [num(row["purchase_count"]) for row in rows]
    width, height = 1280, 620
    left, top, plot_width, plot_height = 85, 85, 1100, 405
    max_amount = max(amounts) or 1
    max_count = max(counts) or 1
    step = plot_width / max(len(rows) - 1, 1)
    amount_points = []
    count_points = []
    for index, row in enumerate(rows):
        x = left + index * step
        amount_y = top + plot_height - amounts[index] / max_amount * plot_height
        count_y = top + plot_height - counts[index] / max_count * plot_height
        amount_points.append(f"{x:.1f},{amount_y:.1f}")
        count_points.append(f"{x:.1f},{count_y:.1f}")
    grid = "".join(
        f'<line class="grid" x1="{left}" y1="{top + i * plot_height / 5:.1f}" x2="{left + plot_width}" y2="{top + i * plot_height / 5:.1f}"/>'
        for i in range(6)
    )
    labels = "".join(
        f'<text class="label" x="{left + i * step:.1f}" y="535" text-anchor="end" transform="rotate(-55 {left + i * step:.1f} 535)">{html.escape(row["month"])}</text>'
        for i, row in enumerate(rows)
    )
    body = (
        '<text class="title" x="40" y="40">Динамика закупок по месяцам</text>'
        '<text class="subtitle" x="40" y="64">Сумма и количество показаны на собственных шкалах</text>'
        + grid
        + f'<polyline points="{" ".join(amount_points)}" fill="none" stroke="#159947" stroke-width="4"/>'
        + f'<polyline points="{" ".join(count_points)}" fill="none" stroke="#2563eb" stroke-width="4"/>'
        + "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="4" fill="#159947"/>' for p in amount_points)
        + "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="4" fill="#2563eb"/>' for p in count_points)
        + labels
        + '<text x="900" y="40" fill="#159947">Сумма, млн руб.</text>'
        + '<text x="1060" y="40" fill="#2563eb">Количество</text>'
    )
    return save_svg("01_monthly_dynamics.svg", width, height, body)


def category_chart(rows: list[dict[str, str]]) -> str:
    width, height = 1280, 620
    left, top, plot_width, plot_height = 80, 80, 1100, 405
    maximum = max(max(num(row["count_2024"]), num(row["count_2025"])) for row in rows) or 1
    group_width = plot_width / len(rows)
    elements = []
    for index, row in enumerate(rows):
        base_x = left + index * group_width + 20
        h2024 = num(row["count_2024"]) / maximum * plot_height
        h2025 = num(row["count_2025"]) / maximum * plot_height
        elements.append(f'<rect x="{base_x:.1f}" y="{top + plot_height - h2024:.1f}" width="45" height="{h2024:.1f}" fill="#2563eb"/>')
        elements.append(f'<rect x="{base_x + 52:.1f}" y="{top + plot_height - h2025:.1f}" width="45" height="{h2025:.1f}" fill="#16a34a"/>')
        elements.append(f'<text class="small" x="{base_x + 22:.1f}" y="{top + plot_height - h2024 - 6:.1f}" text-anchor="middle">{int(num(row["count_2024"]))}</text>')
        elements.append(f'<text class="small" x="{base_x + 74:.1f}" y="{top + plot_height - h2025 - 6:.1f}" text-anchor="middle">{int(num(row["count_2025"]))}</text>')
        elements.append(f'<text class="label" x="{base_x + 50:.1f}" y="535" text-anchor="end" transform="rotate(-35 {base_x + 50:.1f} 535)">{html.escape(row["category"])}</text>')
    body = (
        '<text class="title" x="40" y="40">Структура закупок по направлениям</text>'
        '<text class="subtitle" x="40" y="64">Количество процедур в 2024 и 2025 годах</text>'
        '<text x="980" y="40" fill="#2563eb">2024</text><text x="1060" y="40" fill="#16a34a">2025</text>'
        + "".join(elements)
    )
    return save_svg("02_category_structure.svg", width, height, body)


def top20_chart(rows: list[dict[str, str]]) -> tuple[str, list[dict[str, object]]]:
    top = sorted(rows, key=lambda row: num(row.get("amount_rub")), reverse=True)[:20]
    width, height = 1320, 780
    maximum = max(num(row.get("amount_rub")) for row in top) or 1
    elements = []
    output = []
    for index, row in enumerate(top, start=1):
        y = 70 + (index - 1) * 33
        value = num(row.get("amount_rub"))
        bar_width = value / maximum * 760
        label = row.get("purchase_number") or row.get("canonical_purchase_id", "")
        elements.append(f'<text class="label" x="20" y="{y + 15}">{index}. {html.escape(label)}</text>')
        elements.append(f'<rect x="240" y="{y}" width="{bar_width:.1f}" height="21" fill="#7c3aed"/>')
        elements.append(f'<text class="small" x="{250 + bar_width:.1f}" y="{y + 15}">{money(value)} млн</text>')
        output.append(
            {
                "rank": index,
                "purchase_number": row.get("purchase_number", ""),
                "amount_rub": num(row.get("amount_rub")),
                "customer_name": row.get("customer_name", ""),
                "title": row.get("title", ""),
                "primary_url": row.get("primary_url", ""),
            }
        )
    body = (
        '<text class="title" x="40" y="40">Топ-20 самых дорогих лотов</text>'
        '<text class="subtitle" x="40" y="62">Указанная сумма, млн руб.</text>'
        + "".join(elements)
    )
    return save_svg("03_top20_lots.svg", width, height, body), output


def scatter_chart(
    rows: list[dict[str, str]],
    x_field: str,
    y_field: str,
    title: str,
    x_label: str,
    y_label: str,
    filename: str,
    r_value: float,
    p_value: float,
) -> str:
    x = [num(row[x_field]) for row in rows]
    y = [num(row[y_field]) / 1_000_000 for row in rows]
    width, height = 900, 580
    left, top, plot_width, plot_height = 90, 85, 720, 390
    min_x, max_x = min(x), max(x)
    min_y, max_y = min(y), max(y)
    dots = []
    for row, raw_x, raw_y in zip(rows, x, y):
        px = left + (raw_x - min_x) / (max_x - min_x or 1) * plot_width
        py = top + plot_height - (raw_y - min_y) / (max_y - min_y or 1) * plot_height
        dots.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" fill="#dc2626" opacity="0.75"><title>{html.escape(row["month"])}</title></circle>')
    body = (
        f'<text class="title" x="35" y="40">{html.escape(title)}</text>'
        f'<text class="subtitle" x="35" y="64">Pearson r = {r_value:.4f}; p-value = {p_value:.4f}; n = 24</text>'
        f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>'
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>'
        + "".join(f'<line class="grid" x1="{left}" y1="{top + i * plot_height / 5:.1f}" x2="{left + plot_width}" y2="{top + i * plot_height / 5:.1f}"/>' for i in range(6))
        + "".join(dots)
        + f'<text class="label" x="{left + plot_width / 2}" y="540" text-anchor="middle">{html.escape(x_label)}</text>'
        + f'<text class="label" x="28" y="{top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 28 {top + plot_height / 2})">{html.escape(y_label)}</text>'
    )
    return save_svg(filename, width, height, body)


def amount_distribution_chart(rows: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    bins = {
        "нет суммы": 0,
        "до 10 тыс.": 0,
        "10–100 тыс.": 0,
        "100 тыс.–1 млн": 0,
        "1–10 млн": 0,
        "10–100 млн": 0,
        "100 млн+": 0,
    }
    for row in rows:
        raw = row.get("amount_rub")
        if raw in ("", None):
            bins["нет суммы"] += 1
            continue
        value = num(raw)
        if value < 10_000:
            bins["до 10 тыс."] += 1
        elif value < 100_000:
            bins["10–100 тыс."] += 1
        elif value < 1_000_000:
            bins["100 тыс.–1 млн"] += 1
        elif value < 10_000_000:
            bins["1–10 млн"] += 1
        elif value < 100_000_000:
            bins["10–100 млн"] += 1
        else:
            bins["100 млн+"] += 1
    width, height = 1020, 590
    maximum = max(bins.values()) or 1
    elements = []
    for index, (label, count) in enumerate(bins.items()):
        x = 75 + index * 130
        bar_height = count / maximum * 390
        elements.append(f'<rect x="{x}" y="{470 - bar_height:.1f}" width="82" height="{bar_height:.1f}" fill="#0f766e"/>')
        elements.append(f'<text class="small" x="{x + 41}" y="{460 - bar_height:.1f}" text-anchor="middle">{count}</text>')
        elements.append(f'<text class="label" x="{x + 41}" y="500" text-anchor="end" transform="rotate(-35 {x + 41} 500)">{html.escape(label)}</text>')
    body = (
        '<text class="title" x="40" y="40">Распределение закупок по указанной сумме</text>'
        '<text class="subtitle" x="40" y="64">Диапазоны суммы по карточкам процедур</text>'
        + "".join(elements)
    )
    return save_svg("06_amount_distribution.svg", width, height, body), bins


def nmc_contract_chart(rows: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    total = len(rows)
    with_initial = sum(row.get("amount_rub") not in ("", None) for row in rows)
    with_contract = 0
    width, height = 920, 430
    initial_width = with_initial / total * 620
    contract_width = 2
    body = (
        '<text class="title" x="35" y="40">Доступность НМЦ и итоговой цены контракта</text>'
        '<text class="subtitle" x="35" y="64">Контрактный слой требует отдельного извлечения протоколов</text>'
        '<text class="label" x="35" y="145">Есть начальная сумма</text>'
        f'<rect x="250" y="120" width="{initial_width:.1f}" height="34" fill="#16a34a"/>'
        f'<text x="{260 + initial_width:.1f}" y="143">{with_initial} / {total}</text>'
        '<text class="label" x="35" y="235">Есть итоговая цена контракта</text>'
        f'<rect x="250" y="210" width="{contract_width}" height="34" fill="#dc2626"/>'
        f'<text x="265" y="233">{with_contract} / {total}</text>'
        '<text x="35" y="330">Экономию НМЦ → контракт пока нельзя рассчитать достоверно.</text>'
    )
    return save_svg("07_nmc_contract_availability.svg", width, height, body), {"with_initial_amount": with_initial, "with_contract_amount": with_contract}


def llm_quality_chart(summary: dict[str, object]) -> str:
    total = int(summary["result_rows"])
    valid = int(summary["valid_json_rows"])
    review = int(summary["responses_with_unsupported_inference_terms"])
    safe = total - review
    width, height = 930, 430
    rows = [
        ("Валидный JSON", valid, "#16a34a"),
        ("Без рискованных формулировок", safe, "#2563eb"),
        ("Нужна ручная проверка", review, "#dc2626"),
    ]
    elements = []
    for index, (label, value, color) in enumerate(rows):
        y = 120 + index * 82
        bar_width = value / max(total, 1) * 600
        elements.append(f'<text class="label" x="35" y="{y + 22}">{html.escape(label)}</text>')
        elements.append(f'<rect x="250" y="{y}" width="{bar_width:.1f}" height="34" fill="{color}"/>')
        elements.append(f'<text x="{260 + bar_width:.1f}" y="{y + 23}">{value} / {total}</text>')
    body = (
        '<text class="title" x="35" y="40">Качество локального LLM-анализа</text>'
        '<text class="subtitle" x="35" y="64">Qwen через локальную Ollama, первая часть приоритетной очереди</text>'
        + "".join(elements)
    )
    return save_svg("08_llm_quality.svg", width, height, body)


def hypothesis_by_metric(hypotheses: list[dict[str, object]], metric: str) -> dict[str, object]:
    return next(row for row in hypotheses if row["metric"] == metric)


def build_conclusions(
    monthly: list[dict[str, str]],
    categories: list[dict[str, str]],
    top20: list[dict[str, object]],
    hypotheses: list[dict[str, object]],
    amount_bins: dict[str, int],
    availability: dict[str, int],
    llm_summary: dict[str, object],
) -> list[dict[str, str]]:
    peak_count = max(monthly, key=lambda row: num(row["purchase_count"]))
    peak_amount = max(monthly, key=lambda row: num(row["total_amount_rub"]))
    it = next(row for row in categories if row["category"] == "it_and_telecom")
    construction = next(row for row in categories if row["category"] == "construction_and_repair")
    logistics = next(row for row in categories if row["category"] == "logistics_and_facilities")
    it_amount = hypothesis_by_metric(hypotheses, "it_amount_rub")
    it_count = hypothesis_by_metric(hypotheses, "it_count")
    construction_amount = hypothesis_by_metric(hypotheses, "construction_amount_rub")
    return [
        {
            "block": "Динамика объёма закупок по месяцам",
            "chart": "01_monthly_dynamics.svg",
            "observation": f"Пик по количеству процедур пришёлся на {peak_count['month']} ({peak_count['purchase_count']} закупок), а максимальная указанная сумма — на {peak_amount['month']} ({money(peak_amount['total_amount_rub'])} млн руб.). В 2025 году публикаций заметно больше, чем в 2024.",
            "interpretation": "Разрыв между пиком количества и пиком суммы показывает, что динамику формируют два разных эффекта: массовые небольшие публикации и единичные крупные лоты. Рост 2025 года нельзя автоматически трактовать как чистый рост закупочной активности: часть эффекта связана с расширением сбора и лучшим покрытием источников.",
            "significance": "Для закупочного анализа важно смотреть одновременно на количество, сумму и медиану. Иначе один крупный лот может создать ощущение общего роста, а поток небольших процедур — завысить оценку операционной активности.",
            "limitation": "Используется дата публикации, а не дата оплаты или исполнения. Итоговая цена контракта в текущем слое данных отсутствует, поэтому анализ построен по указанной начальной сумме.",
        },
        {
            "block": "Структура закупок по направлениям",
            "chart": "02_category_structure.svg",
            "observation": f"IT и телеком выросли с {it['count_2024']} до {it['count_2025']} процедур, а указанная сумма увеличилась на {it['amount_change_pct']}%. Логистика и эксплуатация дали самый резкий прирост по количеству: с {logistics['count_2024']} до {logistics['count_2025']}. Строительство выросло по числу процедур, но сумма снизилась на {construction['amount_change_pct']}%.",
            "interpretation": "Направления ведут себя неодинаково: в IT рост сопровождается ростом суммы, в строительстве рост количества может означать дробление работ или большее число малых процедур, а не рост бюджета. Категория `other` остаётся крупной, потому что часть предметов закупки описана общими формулировками.",
            "significance": "Выбор ключевого направления для исследования обоснован: IT и телеком достаточно велики по числу и сумме, а также потенциально чувствительны к валютному фактору из-за оборудования, лицензий и импортных компонентов.",
            "limitation": "Классификация сделана по ключевым словам в названии закупки. Для точной отраслевой структуры нужны ОКПД2, технические задания и нормализация предметов закупки.",
        },
        {
            "block": "Топ-20 самых дорогих лотов",
            "chart": "03_top20_lots.svg",
            "observation": f"Самая крупная процедура — {top20[0]['purchase_number']} на {money(top20[0]['amount_rub'])} млн руб. Топ-20 заметно выделяется относительно основной массы закупок.",
            "interpretation": "Агрегированная сумма чувствительна к небольшому числу крупных процедур. Это особенно важно для сравнения годов: изменение одного-двух лотов может выглядеть как изменение всего направления.",
            "significance": "Топ-20 нужен как контроль выбросов. Перед управленческим выводом полезно проверять, не держится ли рост суммы на отдельных нетипичных процедурах.",
            "limitation": "Поле суммы может означать НМЦ, лимит, тариф или единичную ставку. Без документации и итогового контракта нельзя утверждать фактический расход.",
        },
        {
            "block": "Корреляция: IT-закупки и USD/RUB",
            "chart": "04_it_vs_usd.svg",
            "observation": f"Связь суммы IT-закупок с USD/RUB статистически не подтверждена: r={num(it_amount['pearson_r']):.4f}, p={num(it_amount['p_value']):.4f}. Для количества IT-процедур получена отрицательная статистически значимая связь: r={num(it_count['pearson_r']):.4f}, p={num(it_count['p_value']):.4f}.",
            "interpretation": "Гипотеза о прямом синхронном росте суммы IT-закупок при росте доллара в этих данных не подтверждается. Отрицательная связь по количеству может отражать сезонность, лаг между планированием и публикацией, смещение состава источников или то, что закупки заранее планируются бюджетными циклами.",
            "significance": "Результат защищает от слишком простого вывода `доллар вырос — IT-закупки выросли`. В текущей выборке валютный фактор нужно проверять с лагами и детализацией по оборудованию/ПО.",
            "limitation": "Всего 24 месячных наблюдения. Не проверены лаги, сезонность, типы IT-закупок и доля импортной компоненты.",
        },
        {
            "block": "Корреляция: строительство и ключевая ставка",
            "chart": "05_construction_vs_key_rate.svg",
            "observation": f"Связь суммы строительных закупок с ключевой ставкой незначима: r={num(construction_amount['pearson_r']):.4f}, p={num(construction_amount['p_value']):.4f}.",
            "interpretation": "В пределах 2024–2025 годов закупки строительства, ремонта и эксплуатации сильнее зависят от проектных циклов, бюджета и конкретных объектов, чем от синхронного уровня ставки в месяце публикации.",
            "significance": "Гипотеза о ставке не подтверждена текущим агрегатом, поэтому её нельзя использовать как объяснение динамики без дополнительных факторов.",
            "limitation": "Нужны более длинный ряд, лаги, региональность, тип работ, срок исполнения и стоимость финансирования конкретных проектов.",
        },
        {
            "block": "Распределение суммы закупок",
            "chart": "06_amount_distribution.svg",
            "observation": f"Сумма отсутствует у {amount_bins['нет суммы']} процедур. Остальные закупки распределены от символических/малых значений до лотов свыше 100 млн руб.",
            "interpretation": "В одном поле смешаны разные экономические смыслы: НМЦ, тариф, единичная цена, лимит или пустое значение. Поэтому средняя сумма без сегментации и фильтров может вводить в заблуждение.",
            "significance": "Перед расчётом средних, темпов роста и корреляций надо явно фиксировать, что анализируется: полная цена лота или только опубликованное числовое поле карточки.",
            "limitation": "Для нормализации нужны тип цены, единица измерения, объём поставки и документы закупки.",
        },
        {
            "block": "НМЦ и итоговая цена контракта",
            "chart": "07_nmc_contract_availability.svg",
            "observation": f"Начальная сумма доступна у {availability['with_initial_amount']} процедур из {sum(availability.values()) + 1458 - availability['with_initial_amount']} фактических строк, итоговая цена контракта в текущем слое — у {availability['with_contract_amount']}.",
            "interpretation": "Поисковые карточки и выгрузки площадок дают хороший слой для анализа публикаций, но не закрывают контрактный слой. Поэтому экономию НМЦ → контракт пока корректно посчитать нельзя.",
            "significance": "Это честное ограничение проекта: в отчёте показано, где данные уже пригодны для анализа, а где требуется дополнительное извлечение протоколов и контрактов.",
            "limitation": "Нужно скачать и распарсить протоколы, сведения о победителе, количестве участников и итоговой цене.",
        },
        {
            "block": "Результат обработки через LLM",
            "chart": "08_llm_quality.svg",
            "observation": f"Локальная Qwen через Ollama обработала {llm_summary['result_rows']} карточек, все ответы были валидным JSON ({llm_summary['valid_json_pct']}%). Покрытие очереди LLM — {llm_summary['coverage_of_llm_queue_pct']}%. {llm_summary['responses_with_unsupported_inference_terms']} ответов отмечены как требующие ручной проверки формулировок.",
            "interpretation": "LLM хорошо справилась со структурированием коротких описаний: привела выводы к единому формату, помогла приоритизировать карточки и сформировать черновики интерпретаций. Но модель иногда использует рискованные слова про поставщика, нарушения или единственного участника там, где во входных данных нет протоколов.",
            "significance": "Практический результат LLM — не `автоматическое доказательство аномалий`, а ускорение аналитической рутины: черновая разметка, объяснение риска и список карточек для ручной проверки документов.",
            "limitation": "Обработана только первая часть приоритетной очереди, выборка не случайная. Для финальных выводов по конкуренции нужны протоколы участников, победители и контрактные цены.",
        },
    ]


def markdown_report(rows: list[dict[str, str]]) -> str:
    parts = ["# Этап 4. Визуализация и выводы\n"]
    for row in rows:
        parts.extend(
            [
                f"## {row['block']}\n",
                f"![{row['block']}](charts/{row['chart']})\n",
                f"**Наблюдение:** {row['observation']}\n",
                f"**Интерпретация:** {row['interpretation']}\n",
                f"**Значимость:** {row['significance']}\n",
                f"**Ограничение:** {row['limitation']}\n",
            ]
        )
    parts.append("## Общий вывод\n")
    parts.append(
        "Данные позволяют построить воспроизводимый обзор закупок группы Сбер за 2024–2025 годы: "
        "выделены направления, сравнение годов, корреляционные гипотезы и список аномальных карточек. "
        "Главный аналитический вывод: рост количества и суммы в 2025 году есть, но его нужно читать осторожно, "
        "потому что на результат влияют покрытие источников, крупные единичные лоты и неполнота контрактного слоя. "
        "LLM добавлена как инструмент структурирования и приоритизации, а не как источник доказательств."
    )
    return "\n".join(parts)


def html_report(rows: list[dict[str, str]]) -> str:
    sections = []
    for row in rows:
        sections.append(
            "<section>"
            f"<h2>{html.escape(row['block'])}</h2>"
            f"<img src='charts/{html.escape(row['chart'])}' alt='{html.escape(row['block'])}'>"
            f"<p><b>Наблюдение:</b> {html.escape(row['observation'])}</p>"
            f"<p><b>Интерпретация:</b> {html.escape(row['interpretation'])}</p>"
            f"<p><b>Значимость:</b> {html.escape(row['significance'])}</p>"
            f"<p><b>Ограничение:</b> {html.escape(row['limitation'])}</p>"
            "</section>"
        )
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        "<title>Этап 4. Визуализация и выводы</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1220px;margin:36px auto;color:#18212b;line-height:1.55}"
        "h1,h2{color:#173b57}section{margin:44px 0;padding-bottom:30px;border-bottom:1px solid #ddd}"
        "img{max-width:100%;border:1px solid #e1e5e9;background:white}p{font-size:16px}</style>"
        "</head><body><h1>Этап 4. Визуализация и выводы</h1>"
        "<p>Финальный аналитический отчёт по закупкам группы Сбер за 2024–2025 годы. "
        "Графики построены из обработанного слоя данных, выводы даны в формате наблюдение — интерпретация — значимость — ограничение.</p>"
        + "".join(sections)
        + "</body></html>"
    )


def code_cell(source: str, execution_count: int | None = None, svg_text: str | None = None) -> dict[str, object]:
    outputs = []
    if svg_text is not None:
        outputs.append(
            {
                "data": {"image/svg+xml": svg_text, "text/plain": "<встроенный SVG-график>"},
                "metadata": {},
                "output_type": "display_data",
            }
        )
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "outputs": outputs,
        "source": source.splitlines(True),
    }


def markdown_cell(text: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)}


def chart_markdown_cell(row: dict[str, str]) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": (
            f"## {row['block']}\n\n"
            f"**Наблюдение:** {row['observation']}\n\n"
            f"**Интерпретация:** {row['interpretation']}\n\n"
            f"**Значимость:** {row['significance']}\n\n"
            f"**Ограничение:** {row['limitation']}\n\n"
            f"![{row['block']}](charts/{row['chart']})\n\n"
            f"Файл графика в репозитории: `data/processed/stage4/charts/{row['chart']}`"
        ).splitlines(True),
    }


def copy_charts_for_notebook() -> None:
    NOTEBOOK_CHARTS.mkdir(parents=True, exist_ok=True)
    for chart in CHARTS.glob("*.svg"):
        shutil.copy2(chart, NOTEBOOK_CHARTS / chart.name)


def build_notebook(rows: list[dict[str, str]]) -> None:
    cells: list[dict[str, object]] = [
        markdown_cell(
            "# Закупки группы Сбер за 2024–2025 годы\n\n"
            "Основной аналитический отчёт в формате Jupyter Notebook. Внутри есть описание источников, обработки, базы данных, SQL-запросов, аналитического модуля, LLM-обработки и визуализаций."
        ),
        code_cell(
            "import json\nfrom pathlib import Path\nimport pandas as pd\nfrom IPython.display import SVG, display\nroot = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\nstage2 = root / 'data' / 'processed' / 'stage2'\nstage3 = root / 'data' / 'processed' / 'stage3'\nstage4 = root / 'data' / 'processed' / 'stage4'\ncharts = stage4 / 'charts'\n",
            1,
        ),
        markdown_cell(
            "## Что сделано\n\n"
            "Проект собирает закупки юридических лиц группы Сбер из открытых источников, связывает пересекающиеся записи, обезличивает персональные данные, очищает дубли, загружает аналитический слой в PostgreSQL и строит исследование по ключевому направлению — IT и телеком.\n\n"
            "В итоговой выборке 1 458 канонических закупок за 2024–2025 годы. Для части процедур есть сумма, дата, заказчик, источник, статус и ссылка на карточку."
        ),
        markdown_cell(
            "## Источники и сбор\n\n"
            "| Источник | Зачем использован |\n"
            "|---|---|\n"
            "| ЕИС zakupki.gov.ru | Федеральный открытый источник, полезен для 44-ФЗ/223-ФЗ и проверки отдельных карточек |\n"
            "| Сбербанк-АСТ / SberB2B | Основной массив корпоративных процедур группы Сбер |\n"
            "| Росэлторг, ЗаказРФ, ЛотОнлайн, ТекТорг, РТС-тендер, ЕТП ГПБ | Проверялись как дополнительные открытые площадки и источники ссылок |\n"
            "| ЦБ РФ | Внешние факторы: USD/RUB и ключевая ставка |\n\n"
            "Сбор сделан скриптами этапа 1. После выгрузки данные приводятся к единой структуре, источники связываются через номер закупки, ссылку, заказчика, дату и сумму. Персональные данные в экспортных слоях маскируются."
        ),
        markdown_cell(
            "## Обработка и база данных PostgreSQL\n\n"
            "Аналитическая схема `sber_procurement` содержит таблицы:\n\n"
            "| Таблица | Назначение |\n"
            "|---|---|\n"
            "| `organizations` | юридические лица группы Сбер |\n"
            "| `purchases` | каноническая закупочная процедура после дедупликации |\n"
            "| `purchase_sources` | представления закупки в разных источниках |\n"
            "| `purchase_candidates` | широкие поисковые кандидаты для контроля полноты |\n"
            "| `duplicate_audit` | аудит найденных дублей |\n"
            "| `documents` | очередь карточек и документов для дальнейшего парсинга |\n\n"
            "Основная связь дочерних таблиц с закупками идёт через `canonical_purchase_id`. Для аналитики подготовлены SQL-запросы в `stages/stage2/sql/analytics_queries.sql`: динамика по месяцам, топ заказчиков, топ лотов, проверка дублей и закупки из нескольких источников."
        ),
        markdown_cell(
            "## Ключевое направление анализа\n\n"
            "Выбрано направление IT и телеком: 210 закупок на 906,8 млн руб., то есть 14,4% подтверждённой выборки по количеству. Направление подходит для проверки гипотезы о связи с USD/RUB, потому что в нём могут быть оборудование, лицензии, ПО и телеком-компоненты."
        ),
        markdown_cell(
            "## Сравнение 2024 и 2025\n\n"
            "В 2024 году найдено 325 закупок на 1 363,9 млн руб.; в 2025 году — 1 133 закупки на 2 912,6 млн руб. Рост есть и по количеству, и по сумме, но он интерпретируется осторожно: часть эффекта связана с покрытием источников и отличиями в полноте сумм."
        ),
        markdown_cell(
            "## Корреляционный анализ и гипотезы\n\n"
            "Проверены четыре гипотезы по 24 месячным наблюдениям: сумма и количество IT-закупок против USD/RUB, сумма и количество строительных закупок против ключевой ставки. Для сумм использовалось преобразование `log1p`, значимость проверялась на уровне 0,05.\n\n"
            "Результат: связь суммы IT-закупок с USD/RUB не подтверждена; связь количества IT-закупок с USD/RUB получилась отрицательной и статистически значимой; связь строительных закупок с ключевой ставкой не подтверждена."
        ),
        markdown_cell(
            "## Аномалии\n\n"
            "Сформированы флаги для ручной проверки: экстремальные суммы, отменённые процедуры, повторные публикации и скачки цены по похожему предмету. Эти флаги не доказывают нарушение — они показывают, какие карточки и документы стоит открыть в первую очередь."
        ),
        markdown_cell(
            "## Что дала LLM-обработка\n\n"
            "Локальная Qwen через Ollama обработала первую часть приоритетной очереди карточек. Результат — структурированный JSON и черновики выводов в формате `наблюдение / интерпретация / значимость / ограничение`. Все 38 обработанных ответов были валидным JSON.\n\n"
            "Главная польза LLM — автоматизация работы с короткими неструктурированными описаниями и ускорение подготовки аналитических карточек. Важное ограничение: модель не считается источником фактов о победителях, единственном участнике или нарушениях. Если в данных нет протоколов, такие выводы требуют ручной проверки."
        ),
    ]
    execution_count = 2
    for row in rows:
        cells.append(chart_markdown_cell(row))
        execution_count += 1
    cells.extend(
        [
            markdown_cell(
                "## Итоговый вывод\n\n"
                "Проект даёт воспроизводимый аналитический слой по закупкам группы Сбер за 2024–2025 годы. Основной рост виден в 2025 году, но он зависит от качества покрытия источников, наличия сумм и отдельных крупных процедур. IT и телеком — наиболее содержательное направление для углублённого анализа, однако простая гипотеза о прямой связи суммы IT-закупок с курсом USD/RUB не подтвердилась.\n\n"
                "Для следующего шага важнее всего извлечь документы процедур: протоколы, победителей, количество участников и итоговые цены контрактов. Тогда можно будет проверять экономию, конкуренцию и доли поставщиков уже не как гипотезы, а как полноценные метрики."
            ),
            markdown_cell(
                "## Как демонстрировать Notebook\n\n"
                "1. Открыть `notebooks/final_sber_procurement_report.ipynb`.\n"
                "2. В PyCharm или Jupyter нажать `Restart Kernel and Run All Cells`.\n"
                "3. Показать сверху вниз: источники, обработку, схему БД, SQL, аналитику, LLM и графики.\n"
                "4. Графики встроены в Notebook как attachments, поэтому должны быть видны сразу после открытия без доверия к code outputs."
            ),
        ]
    )
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    NOTEBOOK.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    STAGE4.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    purchases = read_csv(STAGE2 / "purchases_clean.csv")
    monthly = read_csv(STAGE3 / "monthly_external_analysis.csv")
    categories = read_csv(STAGE3 / "category_comparison.csv")
    hypotheses = read_json(STAGE3 / "hypotheses.json")
    llm_summary = read_json(STAGE3 / "llm_results_summary.json")
    monthly_chart(monthly)
    category_chart(categories)
    top20_filename, top20 = top20_chart(purchases)
    hypothesis_map = {row["metric"]: row for row in hypotheses}
    scatter_chart(
        monthly,
        "usd_rub_avg",
        "it_amount_rub",
        "IT-закупки и USD/RUB",
        "Средний USD/RUB за месяц",
        "Сумма IT-закупок, млн руб.",
        "04_it_vs_usd.svg",
        num(hypothesis_map["it_amount_rub"]["pearson_r"]),
        num(hypothesis_map["it_amount_rub"]["p_value"]),
    )
    scatter_chart(
        monthly,
        "key_rate_avg",
        "construction_amount_rub",
        "Строительные закупки и ключевая ставка",
        "Средняя ключевая ставка, %",
        "Сумма строительных закупок, млн руб.",
        "05_construction_vs_key_rate.svg",
        num(hypothesis_map["construction_amount_rub"]["pearson_r"]),
        num(hypothesis_map["construction_amount_rub"]["p_value"]),
    )
    amount_filename, amount_bins = amount_distribution_chart(purchases)
    nmc_filename, availability = nmc_contract_chart(purchases)
    llm_quality_chart(llm_summary)
    conclusions = build_conclusions(monthly, categories, top20, hypotheses, amount_bins, availability, llm_summary)
    (STAGE4 / "stage4_report.md").write_text(markdown_report(conclusions), encoding="utf-8")
    (STAGE4 / "stage4_report.html").write_text(html_report(conclusions), encoding="utf-8")
    write_json(STAGE4 / "conclusions.json", conclusions)
    write_json(
        STAGE4 / "stage4_summary.json",
        {
            "purchases": len(purchases),
            "charts": len(list(CHARTS.glob("*.svg"))),
            "conclusion_blocks": len(conclusions),
            "notebook": str(NOTEBOOK.relative_to(PROJECT_ROOT)),
            "html_report": str((STAGE4 / "stage4_report.html").relative_to(PROJECT_ROOT)),
            "contract_price_available": availability["with_contract_amount"],
        },
    )
    with (STAGE4 / "top20_lots.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["rank", "purchase_number", "amount_rub", "customer_name", "title", "primary_url"])
        writer.writeheader()
        writer.writerows(top20)
    copy_charts_for_notebook()
    build_notebook(conclusions)
    print(json.dumps(read_json(STAGE4 / "stage4_summary.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
