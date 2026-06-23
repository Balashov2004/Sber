from __future__ import annotations

import csv
import html
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STAGE2 = PROJECT_ROOT / "data" / "processed" / "stage2"
STAGE3 = PROJECT_ROOT / "data" / "processed" / "stage3"
OUT = PROJECT_ROOT / "data" / "processed" / "stage4"
CHARTS = OUT / "charts"
NOTEBOOK = PROJECT_ROOT / "notebooks" / "final_sber_procurement_report.ipynb"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def svg(path: Path, width: int, height: int, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        '<style>text{font-family:Arial,sans-serif;fill:#18212b}.title{font-size:24px;font-weight:700}'
        '.subtitle{font-size:13px;fill:#59636e}.axis{stroke:#aab3bd;stroke-width:1}'
        '.grid{stroke:#e6e9ed;stroke-width:1}.label{font-size:12px}.value{font-size:11px}</style>'
        f"{body}</svg>",
        encoding="utf-8",
    )


def monthly_chart(rows: list[dict[str, str]]) -> None:
    width, height = 1280, 620
    left, top, plot_width, plot_height = 80, 80, 1120, 420
    counts = [number(row["purchase_count"]) for row in rows]
    amounts = [number(row["total_amount_rub"]) / 1_000_000 for row in rows]
    max_amount = max(amounts) or 1
    max_count = max(counts) or 1
    grid = "".join(
        f'<line class="grid" x1="{left}" y1="{top + i * plot_height / 5}" x2="{left + plot_width}" '
        f'y2="{top + i * plot_height / 5}"/>'
        for i in range(6)
    )
    labels = "".join(
        f'<text class="label" x="{left + i * plot_width / 23:.1f}" y="530" text-anchor="end" '
        f'transform="rotate(-55 {left + i * plot_width / 23:.1f} 530)">{row["month"]}</text>'
        for i, row in enumerate(rows)
    )
    amount_points = " ".join(
        f"{left + i * plot_width / 23:.1f},{top + plot_height - value * plot_height / max_amount:.1f}"
        for i, value in enumerate(amounts)
    )
    count_points = " ".join(
        f"{left + i * plot_width / 23:.1f},{top + plot_height - value * plot_height / max_count:.1f}"
        for i, value in enumerate(counts)
    )
    body = (
        '<text class="title" x="50" y="38">Динамика закупок по месяцам</text>'
        '<text class="subtitle" x="50" y="60">Сумма приведена к собственной шкале, количество — к собственной</text>'
        + grid
        + f'<polyline points="{amount_points}" fill="none" stroke="#16a34a" stroke-width="4"/>'
        + f'<polyline points="{count_points}" fill="none" stroke="#2563eb" stroke-width="4"/>'
        + labels
        + '<text x="930" y="38" fill="#16a34a">Сумма, млн руб.</text>'
        + '<text x="1080" y="38" fill="#2563eb">Количество</text>'
    )
    svg(CHARTS / "01_monthly_dynamics.svg", width, height, body)


def category_chart(rows: list[dict[str, str]]) -> None:
    rows = rows[:7]
    width, height = 1250, 620
    left, top, plot_width, plot_height = 80, 80, 1080, 430
    maximum = max(number(row["count_2024"]) + number(row["count_2025"]) for row in rows) or 1
    elements = []
    for index, row in enumerate(rows):
        x = left + index * plot_width / len(rows) + 18
        bar_width = 52
        height_2024 = number(row["count_2024"]) / maximum * plot_height
        height_2025 = number(row["count_2025"]) / maximum * plot_height
        elements.extend(
            [
                f'<rect x="{x:.1f}" y="{top + plot_height - height_2024:.1f}" width="{bar_width}" '
                f'height="{height_2024:.1f}" fill="#2563eb"/>',
                f'<rect x="{x + 58:.1f}" y="{top + plot_height - height_2025:.1f}" width="{bar_width}" '
                f'height="{height_2025:.1f}" fill="#16a34a"/>',
                f'<text class="value" x="{x + 26:.1f}" y="{top + plot_height - height_2024 - 7:.1f}" '
                f'text-anchor="middle">{int(number(row["count_2024"]))}</text>',
                f'<text class="value" x="{x + 84:.1f}" y="{top + plot_height - height_2025 - 7:.1f}" '
                f'text-anchor="middle">{int(number(row["count_2025"]))}</text>',
                f'<text class="label" x="{x + 55:.1f}" y="535" text-anchor="end" '
                f'transform="rotate(-35 {x + 55:.1f} 535)">{row["category"]}</text>',
            ]
        )
    body = (
        '<text class="title" x="50" y="38">Структура закупок по направлениям</text>'
        '<text class="subtitle" x="50" y="60">Количество процедур по словарной классификации предмета закупки</text>'
        '<text x="1010" y="38" fill="#2563eb">2024</text><text x="1080" y="38" fill="#16a34a">2025</text>'
        + "".join(elements)
    )
    svg(CHARTS / "02_category_structure.svg", width, height, body)


def top20_chart(purchases: list[dict[str, str]]) -> list[dict[str, object]]:
    top = sorted(purchases, key=lambda row: number(row.get("amount_rub")), reverse=True)[:20]
    width, height = 1300, 760
    maximum = number(top[0]["amount_rub"]) if top else 1
    elements = []
    output = []
    for index, row in enumerate(top):
        y = 65 + index * 33
        value = number(row["amount_rub"])
        bar_width = value / maximum * 730
        title = row.get("title", "")
        output.append(
            {
                "rank": index + 1,
                "purchase_number": row.get("purchase_number", ""),
                "amount_rub": value,
                "customer_name": row.get("customer_name", ""),
                "title": title,
                "primary_url": row.get("primary_url", ""),
            }
        )
        elements.append(
            f'<text class="label" x="15" y="{y + 15}">{index + 1}. {html.escape(str(row.get("purchase_number", "")))}</text>'
            f'<rect x="215" y="{y}" width="{bar_width:.1f}" height="20" fill="#7c3aed"/>'
            f'<text class="value" x="{225 + bar_width:.1f}" y="{y + 15}">{value / 1_000_000:.1f}</text>'
        )
    body = (
        '<text class="title" x="30" y="35">Топ-20 самых дорогих закупок</text>'
        '<text class="subtitle" x="30" y="55">Указанная начальная сумма, млн руб.</text>'
        + "".join(elements)
    )
    svg(CHARTS / "03_top20_lots.svg", width, height, body)
    return output


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
    log_y: bool,
) -> None:
    pairs = []
    for row in rows:
        x = number(row[x_field])
        y = number(row[y_field])
        if log_y:
            y = math.log1p(y)
        pairs.append((x, y, row["month"]))
    min_x, max_x = min(x for x, _, _ in pairs), max(x for x, _, _ in pairs)
    min_y, max_y = min(y for _, y, _ in pairs), max(y for _, y, _ in pairs)
    width, height = 850, 570
    left, top, plot_width, plot_height = 90, 80, 680, 390
    dots = []
    for x, y, month in pairs:
        px = left + (x - min_x) / (max_x - min_x or 1) * plot_width
        py = top + plot_height - (y - min_y) / (max_y - min_y or 1) * plot_height
        dots.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" fill="#dc2626" opacity="0.72">'
            f"<title>{month}: x={x:.2f}, y={y:.2f}</title></circle>"
        )
    body = (
        f'<text class="title" x="35" y="35">{html.escape(title)}</text>'
        f'<text class="subtitle" x="35" y="58">Pearson r={r_value:.4f}; permutation p={p_value:.4f}; n=24</text>'
        f'<line class="axis" x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}"/>'
        f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}"/>'
        + "".join(dots)
        + f'<text class="label" x="{left + plot_width / 2}" y="535" text-anchor="middle">{html.escape(x_label)}</text>'
        + f'<text class="label" x="20" y="{top + plot_height / 2}" text-anchor="middle" '
        f'transform="rotate(-90 20 {top + plot_height / 2})">{html.escape(y_label)}</text>'
    )
    svg(CHARTS / filename, width, height, body)


def amount_distribution_chart(purchases: list[dict[str, str]]) -> dict[str, int]:
    bins = [
        ("Нет суммы", None, None),
        ("до 10 тыс.", 0, 10_000),
        ("10–100 тыс.", 10_000, 100_000),
        ("100 тыс.–1 млн", 100_000, 1_000_000),
        ("1–10 млн", 1_000_000, 10_000_000),
        ("10–100 млн", 10_000_000, 100_000_000),
        ("100 млн+", 100_000_000, math.inf),
    ]
    counts = {label: 0 for label, _, _ in bins}
    for row in purchases:
        raw = row.get("amount_rub", "")
        if raw in ("", None):
            counts["Нет суммы"] += 1
            continue
        value = number(raw)
        for label, lower, upper in bins[1:]:
            if lower <= value < upper:
                counts[label] += 1
                break
    width, height = 1000, 580
    maximum = max(counts.values()) or 1
    elements = []
    for index, (label, count) in enumerate(counts.items()):
        x = 70 + index * 130
        bar_height = count / maximum * 390
        elements.append(
            f'<rect x="{x}" y="{470 - bar_height:.1f}" width="82" height="{bar_height:.1f}" fill="#0f766e"/>'
            f'<text class="value" x="{x + 41}" y="{460 - bar_height:.1f}" text-anchor="middle">{count}</text>'
            f'<text class="label" x="{x + 41}" y="495" text-anchor="end" '
            f'transform="rotate(-35 {x + 41} 495)">{label}</text>'
        )
    body = (
        '<text class="title" x="35" y="35">Распределение закупок по указанной сумме</text>'
        '<text class="subtitle" x="35" y="58">Логарифмические диапазоны; нулевые и символические цены сохранены</text>'
        + "".join(elements)
    )
    svg(CHARTS / "06_amount_distribution.svg", width, height, body)
    return counts


def contract_gap_chart(purchases: list[dict[str, str]]) -> dict[str, int]:
    with_initial = sum(row.get("amount_rub") not in ("", None) for row in purchases)
    with_contract = 0
    width, height = 900, 430
    initial_width = with_initial / len(purchases) * 650
    body = (
        '<text class="title" x="35" y="38">Доступность данных НМЦ и итоговой цены контракта</text>'
        '<text class="subtitle" x="35" y="62">Итоговая цена отсутствует в текущем слое данных</text>'
        f'<text class="label" x="35" y="145">Указанная начальная сумма</text>'
        f'<rect x="220" y="118" width="{initial_width:.1f}" height="38" fill="#16a34a"/>'
        f'<text x="{230 + initial_width:.1f}" y="144">{with_initial} / {len(purchases)}</text>'
        '<text class="label" x="35" y="235">Итоговая цена контракта</text>'
        '<rect x="220" y="208" width="2" height="38" fill="#dc2626"/>'
        f'<text x="235" y="234">{with_contract} / {len(purchases)}</text>'
        '<text x="35" y="325" font-size="15">Распределение экономии НМЦ → контракт нельзя построить достоверно.</text>'
        '<text x="35" y="352" font-size="15">Нужно извлечь contract_price, winner и protocol_url из протоколов.</text>'
    )
    svg(CHARTS / "07_nmc_contract_availability.svg", width, height, body)
    return {"with_initial_amount": with_initial, "with_contract_amount": with_contract}


def llm_quality_chart(summary: dict[str, object]) -> None:
    total = int(summary["result_rows"])
    valid = int(summary["valid_json_rows"])
    manual = int(summary["responses_with_unsupported_inference_terms"])
    safe = total - manual
    width, height = 900, 430
    body = (
        '<text class="title" x="35" y="38">Качество локального LLM-анализа</text>'
        '<text class="subtitle" x="35" y="62">Qwen 3.5 9B, первые задачи приоритетной очереди</text>'
        f'<text class="label" x="35" y="140">Валидный JSON</text><rect x="220" y="115" width="{valid / total * 600:.1f}" '
        f'height="36" fill="#16a34a"/><text x="830" y="140">{valid}/{total}</text>'
        f'<text class="label" x="35" y="220">Без рискованных формулировок</text><rect x="220" y="195" '
        f'width="{safe / total * 600:.1f}" height="36" fill="#2563eb"/><text x="830" y="220">{safe}/{total}</text>'
        f'<text class="label" x="35" y="300">Нужна ручная проверка</text><rect x="220" y="275" '
        f'width="{manual / total * 600:.1f}" height="36" fill="#dc2626"/><text x="830" y="300">{manual}/{total}</text>'
    )
    svg(CHARTS / "08_llm_quality.svg", width, height, body)


def conclusions(
    monthly: list[dict[str, str]],
    categories: list[dict[str, str]],
    top20: list[dict[str, object]],
    hypotheses: list[dict[str, object]],
    amount_bins: dict[str, int],
    availability: dict[str, int],
    llm_summary: dict[str, object],
) -> list[dict[str, str]]:
    peak_count = max(monthly, key=lambda row: number(row["purchase_count"]))
    peak_amount = max(monthly, key=lambda row: number(row["total_amount_rub"]))
    it = next(row for row in categories if row["category"] == "it_and_telecom")
    construction = next(row for row in categories if row["category"] == "construction_and_repair")
    it_amount_h = next(row for row in hypotheses if row["metric"] == "it_amount_rub")
    it_count_h = next(row for row in hypotheses if row["metric"] == "it_count")
    construction_h = next(row for row in hypotheses if row["metric"] == "construction_amount_rub")
    return [
        {
            "block": "Динамика по месяцам",
            "chart": "01_monthly_dynamics.svg",
            "observation": f"Максимум количества пришёлся на {peak_count['month']} ({peak_count['purchase_count']} процедур), максимум суммы — на {peak_amount['month']} ({number(peak_amount['total_amount_rub']) / 1_000_000:.1f} млн руб.).",
            "interpretation": "Рост во второй половине 2025 года может сочетать сезонность закупочного цикла и более полное покрытие площадки.",
            "significance": "Месяцы-пики нельзя оценивать только по сумме: необходимо отделять массовую публикацию небольших процедур от единичных крупных лотов.",
            "limitation": "Дата публикации не отражает дату оплаты или фактического исполнения контракта.",
        },
        {
            "block": "Структура направлений",
            "chart": "02_category_structure.svg",
            "observation": f"IT и телеком выросли с {it['count_2024']} до {it['count_2025']} процедур, указанная сумма — на {it['amount_change_pct']}%. Строительство выросло по количеству, но сумма изменилась на {construction['amount_change_pct']}%.",
            "interpretation": "Рост количества не всегда означает рост денежного объёма; структура и масштаб процедур меняются по-разному.",
            "significance": "Направления необходимо сравнивать одновременно по количеству, сумме и медиане.",
            "limitation": "Словарная классификация не заменяет ОКПД2 и проверку технических заданий.",
        },
        {
            "block": "Топ-20",
            "chart": "03_top20_lots.svg",
            "observation": f"Самая крупная процедура — {top20[0]['purchase_number']} на {number(top20[0]['amount_rub']) / 1_000_000:.1f} млн руб.",
            "interpretation": "Совокупная сумма чувствительна к небольшому числу крупных процедур.",
            "significance": "Для устойчивых выводов следует показывать медиану и проводить анализ с исключением крупнейших наблюдений.",
            "limitation": "Указанная сумма может быть НМЦ, лимитом, тарифом или единичной расценкой.",
        },
        {
            "block": "IT и USD/RUB",
            "chart": "04_it_vs_usd.svg",
            "observation": f"Для суммы IT-закупок связь незначима: r={it_amount_h['pearson_r']}, p={it_amount_h['p_value']}. Для количества процедур получена отрицательная связь: r={it_count_h['pearson_r']}, p={it_count_h['p_value']}.",
            "interpretation": "Синхронная месячная сумма не следует за курсом; количество может отражать сезонность или изменение покрытия, а не прямой валютный эффект.",
            "significance": "Статистическая проверка предотвращает ошибочный вывод по визуальному совпадению линий.",
            "limitation": "Всего 24 месяца; не проверены лаги, сезонность и состав импортной компоненты.",
        },
        {
            "block": "Строительство и ключевая ставка",
            "chart": "05_construction_vs_key_rate.svg",
            "observation": f"Связь суммы строительных закупок с ключевой ставкой незначима: r={construction_h['pearson_r']}, p={construction_h['p_value']}.",
            "interpretation": "В пределах двух лет закупочная активность определяется не только стоимостью денег, но и бюджетами, проектными циклами и отдельными объектами.",
            "significance": "Гипотеза не подтверждена текущей выборкой и не должна подаваться как установленная закономерность.",
            "limitation": "Двадцать четыре наблюдения недостаточны для устойчивой модели с лагами и контролем сезонности.",
        },
        {
            "block": "Распределение сумм",
            "chart": "06_amount_distribution.svg",
            "observation": f"Сумма отсутствует у {amount_bins['Нет суммы']} процедур; распределение охватывает диапазон от символических значений до лотов свыше 100 млн руб.",
            "interpretation": "В одном поле смешаны разные экономические смыслы: полная НМЦ, тариф, единичная цена и незаполненное значение.",
            "significance": "Среднее значение без очистки и сегментации будет вводить в заблуждение.",
            "limitation": "Для нормализации нужны единица измерения, объём, тип цены и документы процедуры.",
        },
        {
            "block": "НМЦ → контракт",
            "chart": "07_nmc_contract_availability.svg",
            "observation": f"Начальная сумма доступна у {availability['with_initial_amount']} процедур, итоговая цена контракта — у {availability['with_contract_amount']}.",
            "interpretation": "Текущие поисковые карточки не содержат достаточного контрактного слоя.",
            "significance": "Экономию, снижение цены и эффективность конкуренции нельзя рассчитывать без итоговой цены.",
            "limitation": "Требуется извлечение протоколов, победителя, числа участников и суммы заключённого контракта.",
        },
        {
            "block": "LLM",
            "chart": "08_llm_quality.svg",
            "observation": f"Qwen сформировала {llm_summary['valid_json_rows']} валидных JSON из {llm_summary['result_rows']}, но {llm_summary['responses_with_unsupported_inference_terms']} ответов требуют ручной проверки формулировок.",
            "interpretation": "Модель хорошо структурирует текст, но склонна усиливать риск-флаги до неподтверждённых предположений.",
            "significance": "LLM полезна как черновик и инструмент приоритизации, а не как источник фактов о нарушениях.",
            "limitation": "Обработано только 8,41% приоритетной очереди; выборка неслучайная.",
        },
    ]


def save_top20(rows: list[dict[str, object]]) -> None:
    with (OUT / "top20_lots.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_conclusions(rows: list[dict[str, str]]) -> None:
    (OUT / "conclusions.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    parts = ["# Этап 4. Визуализация и выводы", ""]
    for row in rows:
        parts.extend(
            [
                f"## {row['block']}",
                "",
                f"![{row['block']}](charts/{row['chart']})",
                "",
                f"**Наблюдение:** {row['observation']}",
                "",
                f"**Интерпретация:** {row['interpretation']}",
                "",
                f"**Значимость:** {row['significance']}",
                "",
                f"**Ограничение:** {row['limitation']}",
                "",
            ]
        )
    (OUT / "stage4_report.md").write_text("\n".join(parts), encoding="utf-8")


def build_notebook(rows: list[dict[str, str]]) -> None:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Закупки группы Сбер за 2024–2025 годы\n",
                "## Финальный аналитический отчёт\n",
                "Отчёт объединяет сбор открытых данных, связывание источников, обезличивание, PostgreSQL, проверку гипотез, обнаружение аномалий, локальную Qwen и визуализации.",
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
                "out = root / 'data' / 'processed' / 'stage4'\n",
                "stage2 = root / 'data' / 'processed' / 'stage2'\n",
                "stage3 = root / 'data' / 'processed' / 'stage3'\n",
                "conclusions = json.loads((out / 'conclusions.json').read_text(encoding='utf-8'))\n",
                "summary = json.loads((out / 'stage4_summary.json').read_text(encoding='utf-8'))\n",
                "summary\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Постановка задачи\n",
                "Цель проекта — собрать и связать открытые сведения о закупках юридических лиц группы Сбер за 2024–2025 годы, очистить данные, спроектировать PostgreSQL, проверить аналитические гипотезы и подготовить воспроизводимый отчёт.\n",
                "\n",
                "В основной аналитический слой включаются только процедуры, где заказчик или организатор подтверждён по ИНН. Простого упоминания слова «Сбербанк» в тексте недостаточно.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Установка и кнопки запуска\n",
                "\n",
                "Перед первым запуском необходимо установить Python 3.12 и выполнить `setup_environment.cmd`. Для базы устанавливается PostgreSQL 16. Для локального LLM устанавливаются Ollama и модель `qwen3.5:9b`.\n",
                "\n",
                "| Файл | Назначение |\n",
                "|---|---|\n",
                "| `setup_environment.cmd` | Создание `.venv` и установка зависимостей |\n",
                "| `start_project.cmd` | Единое меню проекта |\n",
                "| `update_database.cmd` | Обновление PostgreSQL |\n",
                "| `run_stage3_qwen.cmd` | Следующая порция Qwen |\n",
                "| `run_stage4.cmd` | Пересбор финального отчёта |\n",
                "| `open_notebook.cmd` | Открытие этого Notebook |\n",
                "\n",
                "### Настройка Qwen\n",
                "\n",
                "```powershell\n",
                "ollama --version\n",
                "ollama pull qwen3.5:9b\n",
                "ollama list\n",
                ".\\run_stage3_qwen.ps1 -Limit 25\n",
                "```\n",
                "\n",
                "Результат каждой задачи записывается сразу, поэтому выполнение можно прерывать и продолжать.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Рекомендуемый порядок запуска\n",
                "\n",
                "```text\n",
                "1. setup_environment.cmd\n",
                "2. start_project.cmd\n",
                "3. Пункт 7: Этапы 2, 3 и 4\n",
                "4. Пункт 2: загрузка PostgreSQL\n",
                "5. Пункт 4: Qwen при необходимости\n",
                "6. Пункт 5: повторная сборка отчёта после Qwen\n",
                "7. Пункт 6: открыть Jupyter\n",
                "```\n",
                "\n",
                "Сбор данных из интернета выполняется отдельно и занимает больше времени. Для демонстрации используются уже сохранённые обезличенные результаты.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Источники данных\n",
                "\n",
                "| Источник | Роль |\n",
                "|---|---|\n",
                "| Сбербанк-АСТ и SberB2B | Основной массив корпоративных процедур, даты, суммы, статусы и ссылки |\n",
                "| ЕИС | Официальные карточки отдельных процедур 44-ФЗ и 223-ФЗ, независимая сверка |\n",
                "| ФНС ЕГРЮЛ | Проверка ИНН, КПП, ОГРН и юридических наименований |\n",
                "| ЗаказРФ, Росэлторг, ЛотОнлайн, ТЭК-Торг, РТС-тендер, ЭТП ГПБ | Проверка дополнительного покрытия |\n",
                "| Банк России | Ежедневный USD/RUB и ключевая ставка |\n",
                "\n",
                "Сбербанк-АСТ выбран основным источником из-за наибольшего числа подтверждённых процедур группы. ЕИС используется для межисточникового контроля. Остальные площадки входят в автоматический журнал проверки источников.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Как собирались и обрабатывались данные\n",
                "\n",
                "```text\n",
                "Открытые площадки\n",
                "        ↓\n",
                "Поисковые результаты и карточки\n",
                "        ↓\n",
                "Проверка заказчика по реестру ИНН\n",
                "        ↓\n",
                "Связывание по точному номеру закупки\n",
                "        ↓\n",
                "Обогащение реквизитами ЕГРЮЛ\n",
                "        ↓\n",
                "Обезличивание ФИО, телефонов, почты, паспортов и СНИЛС\n",
                "        ↓\n",
                "Дедупликация и аналитический слой\n",
                "        ↓\n",
                "PostgreSQL, гипотезы, аномалии, LLM и графики\n",
                "```\n",
                "\n",
                "Удаление дублей выполняется только по точному идентификатору и подтверждённой связи источников. Текстовое сходство используется как сигнал для ручной проверки, но не как основание удаления.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Описание собранных данных\n",
                "\n",
                "- 17 проверенных организаций;\n",
                "- 1 458 канонических закупок;\n",
                "- 325 процедур за 2024 год;\n",
                "- 1 133 процедуры за 2025 год;\n",
                "- 1 461 строка источников;\n",
                "- 3 точных межисточниковых дубля;\n",
                "- 6 302 кандидата отделены от подтверждённой аналитики;\n",
                "- сумма заполнена у 1 180 процедур;\n",
                "- итоговая цена контракта в текущем слое отсутствует.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Устройство PostgreSQL\n",
                "\n",
                "Схема базы называется `sber_procurement`.\n",
                "\n",
                "| Таблица | Зерно и назначение | Строк |\n",
                "|---|---|---:|\n",
                "| `organizations` | Одно юридическое лицо группы Сбер | 17 |\n",
                "| `purchases` | Одна каноническая закупочная процедура | 1 458 |\n",
                "| `purchase_sources` | Одно представление закупки на одной площадке | 1 461 |\n",
                "| `purchase_candidates` | Один неподтверждённый поисковый результат | 6 302 |\n",
                "| `duplicate_audit` | Одна подтверждённая связь дублирующих источников | 3 |\n",
                "| `documents` | Одна карточка или вложение в очереди обработки | 1 461 |\n",
                "\n",
                "```text\n",
                "purchases\n",
                "  ├── purchase_sources\n",
                "  ├── duplicate_audit\n",
                "  └── documents\n",
                "\n",
                "organizations        purchase_candidates\n",
                "```\n",
                "\n",
                "Связь дочерних таблиц с закупкой выполняется через `canonical_purchase_id`. Индексы созданы по дате, ИНН заказчика, сумме и году/месяцу.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Представления PostgreSQL\n",
                "\n",
                "- `v_monthly_dynamics` — число закупок, сумма и медиана по месяцам;\n",
                "- `v_customer_summary` — число и сумма закупок по заказчикам.\n",
                "\n",
                "Структура создаётся файлом `stages/stage2/sql/schema.sql`, загрузка выполняется через `load_data.psql`.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Примеры аналитических SQL-запросов\n",
                "\n",
                "### Сравнение по годам\n",
                "\n",
                "```sql\n",
                "SELECT year,\n",
                "       count(*) AS purchase_count,\n",
                "       sum(amount_rub) AS total_amount_rub\n",
                "FROM sber_procurement.purchases\n",
                "GROUP BY year\n",
                "ORDER BY year;\n",
                "```\n",
                "\n",
                "### Топ-20 закупок\n",
                "\n",
                "```sql\n",
                "SELECT purchase_number, customer_name, amount_rub, title\n",
                "FROM sber_procurement.purchases\n",
                "WHERE amount_rub IS NOT NULL\n",
                "ORDER BY amount_rub DESC\n",
                "LIMIT 20;\n",
                "```\n",
                "\n",
                "### Аудит дублей\n",
                "\n",
                "```sql\n",
                "SELECT duplicate_type, match_method, count(*)\n",
                "FROM sber_procurement.duplicate_audit\n",
                "GROUP BY duplicate_type, match_method;\n",
                "```\n",
                "\n",
                "### Закупки из нескольких источников\n",
                "\n",
                "```sql\n",
                "SELECT canonical_purchase_id,\n",
                "       count(*) AS source_count,\n",
                "       string_agg(source_system, ' | ' ORDER BY source_system)\n",
                "FROM sber_procurement.purchase_sources\n",
                "GROUP BY canonical_purchase_id\n",
                "HAVING count(*) > 1;\n",
                "```\n",
                "\n",
                "Полный набор находится в `stages/stage2/sql/analytics_queries.sql`.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Аналитические гипотезы\n",
                "\n",
                "1. Сумма и количество IT-закупок связаны с USD/RUB.\n",
                "2. Сумма и количество строительных закупок связаны с ключевой ставкой.\n",
                "3. Крупнейшие процедуры существенно влияют на агрегированную сумму.\n",
                "4. Рост количества публикаций и рост денежного объёма могут расходиться.\n",
                "\n",
                "Для сумм применяется `log1p`. Коэффициент Пирсона проверяется перестановочным тестом на 10 000 перестановок. Уровень значимости — 0,05.",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Обнаружение аномалий\n",
                "\n",
                "Проверяются экстремальные суммы, отмены, повторные публикации, конфликты статуса и скачки цены похожего предмета. Сигнал не является доказательством нарушения и используется только для приоритизации проверки карточек и документов.",
            ],
        },
    ]
    chart_execution_count = 2
    for row in rows:
        chart_path = CHARTS / row["chart"]
        chart_svg = chart_path.read_text(encoding="utf-8")
        cells.append(
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"## {row['block']}\n",
                    f"**Наблюдение:** {row['observation']}  \n",
                    f"**Интерпретация:** {row['interpretation']}  \n",
                    f"**Значимость:** {row['significance']}  \n",
                    f"**Ограничение:** {row['limitation']}",
                ],
            }
        )
        cells.append(
            {
                "cell_type": "code",
                "execution_count": chart_execution_count,
                "metadata": {
                    "jupyter": {"source_hidden": True},
                    "tags": ["hide-input"],
                },
                "outputs": [
                    {
                        "data": {
                            "image/svg+xml": chart_svg,
                            "text/plain": f"<Визуализация: {row['block']}>",
                        },
                        "metadata": {},
                        "output_type": "display_data",
                    }
                ],
                "source": [
                    "from IPython.display import SVG, display\n",
                    f"display(SVG(filename=str(root / 'data' / 'processed' / 'stage4' / 'charts' / '{row['chart']}')))\n",
                ],
            }
        )
        chart_execution_count += 1
    cells.extend(
        [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Роль локальной Qwen\n",
                    "\n",
                    "Qwen 3.5 9B запускается локально через Ollama. Модель формирует структурированный JSON и черновик вывода. Она не используется как источник фактов об участниках, победителях, единственном поставщике или нарушениях. Ответы проходят отдельный аудит рискованных формулировок.",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Общий вывод\n",
                    "\n",
                    "В 2025 году число подтверждённых публикаций и указанная сумма выше, однако часть различия может быть связана с покрытием источника. IT и телеком являются ключевым содержательным направлением. Связь суммы IT-закупок с USD/RUB не подтверждена, как и связь строительной суммы с ключевой ставкой. Агрегаты чувствительны к отдельным крупным процедурам и неоднородному смыслу поля суммы.\n",
                    "\n",
                    "Для полноценного анализа конкуренции и экономии необходимо извлечь протоколы, число участников, победителя и итоговую цену контракта. LLM полезна для структурирования и приоритизации, но её риск-выводы требуют ручной проверки.",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "## Воспроизводимый запуск\n",
                    "\n",
                    "```powershell\n",
                    "python stages\\stage1\\scripts\\build_stage1_dataset.py\n",
                    "python stages\\stage1\\scripts\\anonymize_exports.py\n",
                    "python stages\\stage1\\scripts\\enrich_multisource.py\n",
                    "python stages\\stage2\\scripts\\process_stage2.py\n",
                    ".\\update_database.cmd\n",
                    "python stages\\stage3\\scripts\\analyze_stage3.py\n",
                    "python stages\\stage3\\scripts\\summarize_llm_results.py\n",
                    "python stages\\stage4\\scripts\\build_stage4.py\n",
                    "```\n",
                    "\n",
                    "Для демонстрации достаточно открыть этот Notebook, выполнить `Restart Kernel and Run All Cells`, а затем последовательно показать методологию, схему базы, SQL и графики.",
                ],
            },
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


def build_html(rows: list[dict[str, str]]) -> None:
    sections = []
    for row in rows:
        sections.append(
            f"<section><h2>{html.escape(row['block'])}</h2>"
            f"<img src='charts/{row['chart']}' alt='{html.escape(row['block'])}'>"
            f"<p><b>Наблюдение:</b> {html.escape(row['observation'])}</p>"
            f"<p><b>Интерпретация:</b> {html.escape(row['interpretation'])}</p>"
            f"<p><b>Значимость:</b> {html.escape(row['significance'])}</p>"
            f"<p><b>Ограничение:</b> {html.escape(row['limitation'])}</p></section>"
        )
    document = (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Этап 4</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:35px auto;color:#18212b;"
        "line-height:1.5}h1,h2{color:#173b57}section{margin:45px 0;padding-bottom:30px;"
        "border-bottom:1px solid #ddd}img{max-width:100%;border:1px solid #e1e5e9;background:white}"
        "p{font-size:16px}</style></head><body><h1>Этап 4. Визуализация и выводы</h1>"
        "<p>Финальный аналитический отчёт по закупкам группы Сбер за 2024–2025 годы.</p>"
        + "".join(sections)
        + "</body></html>"
    )
    (OUT / "stage4_report.html").write_text(document, encoding="utf-8")


def main() -> None:
    purchases = read_csv(STAGE2 / "purchases_clean.csv")
    monthly = read_csv(STAGE3 / "monthly_external_analysis.csv")
    categories = read_csv(STAGE3 / "category_comparison.csv")
    hypotheses = read_json(STAGE3 / "hypotheses.json")
    llm_summary = read_json(STAGE3 / "llm_results_summary.json")
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    monthly_chart(monthly)
    category_chart(categories)
    top20 = top20_chart(purchases)
    hypothesis_map = {str(row["metric"]): row for row in hypotheses}
    scatter_chart(
        monthly,
        "usd_rub_avg",
        "it_amount_rub",
        "Сумма IT-закупок и USD/RUB",
        "Средний USD/RUB",
        "log(1 + сумма IT-закупок)",
        "04_it_vs_usd.svg",
        number(hypothesis_map["it_amount_rub"]["pearson_r"]),
        number(hypothesis_map["it_amount_rub"]["p_value"]),
        True,
    )
    scatter_chart(
        monthly,
        "key_rate_avg",
        "construction_amount_rub",
        "Строительные закупки и ключевая ставка",
        "Средняя ключевая ставка, %",
        "log(1 + сумма строительных закупок)",
        "05_construction_vs_key_rate.svg",
        number(hypothesis_map["construction_amount_rub"]["pearson_r"]),
        number(hypothesis_map["construction_amount_rub"]["p_value"]),
        True,
    )
    amount_bins = amount_distribution_chart(purchases)
    availability = contract_gap_chart(purchases)
    llm_quality_chart(llm_summary)
    rows = conclusions(
        monthly,
        categories,
        top20,
        hypotheses,
        amount_bins,
        availability,
        llm_summary,
    )
    save_top20(top20)
    save_conclusions(rows)
    build_notebook(rows)
    build_html(rows)
    summary = {
        "purchases": len(purchases),
        "charts": len(list(CHARTS.glob("*.svg"))),
        "conclusion_blocks": len(rows),
        "notebook": str(NOTEBOOK.relative_to(PROJECT_ROOT)),
        "html_report": str((OUT / "stage4_report.html").relative_to(PROJECT_ROOT)),
        "contract_price_available": availability["with_contract_amount"],
    }
    (OUT / "stage4_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
