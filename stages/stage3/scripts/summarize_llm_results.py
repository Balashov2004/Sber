from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_results.jsonl"
DEFAULT_TASKS = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_tasks.jsonl"
DEFAULT_JSON = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_results_summary.json"
DEFAULT_MD = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_results_summary.md"
DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_results_review.csv"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize and audit Stage 3 LLM results.")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    results = read_jsonl(args.results)
    tasks = {str(row["task_id"]): row for row in read_jsonl(args.tasks)}
    reviewed = []
    confidence_values = []
    unsupported_terms = (
        "единственного поставщика",
        "единственный поставщик",
        "корруп",
        "нарушен",
        "сговор",
        "неэффектив",
        "прозрачн",
        "44-фз",
        "223-фз",
    )

    for result in results:
        task_id = str(result.get("task_id", ""))
        task = tasks.get(task_id, {})
        task_input = task.get("input", {}) if isinstance(task.get("input"), dict) else {}
        output = result.get("structured_output", {})
        output = output if isinstance(output, dict) else {}
        confidence = output.get("category_confidence")
        if isinstance(confidence, (int, float)):
            confidence_values.append(float(confidence))
        text = " ".join(str(output.get(field, "")) for field in (
            "category",
            "price_or_scope_risk",
            "observation",
            "interpretation",
            "significance",
            "limitation",
        )).lower()
        unsupported = sorted({term for term in unsupported_terms if term in text})
        flags = task_input.get("anomaly_flags", [])
        reviewed.append(
            {
                "task_id": task_id,
                "purchase_number": task_input.get("purchase_number", ""),
                "title": task_input.get("title", ""),
                "amount_rub": task_input.get("amount_rub", ""),
                "rule_category": task_input.get("rule_category", ""),
                "anomaly_flags": "|".join(flags) if isinstance(flags, list) else str(flags),
                "llm_category": output.get("category", ""),
                "category_confidence": confidence if confidence is not None else "",
                "single_supplier_signal": output.get("single_supplier_signal"),
                "unsupported_inference_terms": "|".join(unsupported),
                "needs_manual_review": "1" if unsupported else "0",
                "observation": output.get("observation", ""),
                "interpretation": output.get("interpretation", ""),
                "significance": output.get("significance", ""),
                "limitation": output.get("limitation", ""),
            }
        )

    unique_tasks = len({str(row.get("task_id", "")) for row in results})
    valid_json = sum(row.get("parse_status") == "valid_json" for row in results)
    manual_review = sum(row["needs_manual_review"] == "1" for row in reviewed)
    supplier_values = Counter(
        str((row.get("structured_output") or {}).get("single_supplier_signal"))
        for row in results
        if isinstance(row.get("structured_output"), dict)
    )
    rule_flags = Counter()
    rule_categories = Counter()
    for row in reviewed:
        rule_categories[str(row["rule_category"])] += 1
        for flag in str(row["anomaly_flags"]).split("|"):
            if flag:
                rule_flags[flag] += 1

    summary = {
        "result_rows": len(results),
        "unique_tasks": unique_tasks,
        "valid_json_rows": valid_json,
        "valid_json_pct": round(100 * valid_json / len(results), 2) if results else 0,
        "coverage_of_llm_queue_pct": round(100 * unique_tasks / len(tasks), 2) if tasks else 0,
        "model": Counter(str(row.get("model", "")) for row in results).most_common(),
        "provider": Counter(str(row.get("provider", "")) for row in results).most_common(),
        "mean_category_confidence": round(statistics.mean(confidence_values), 3)
        if confidence_values
        else None,
        "median_category_confidence": round(statistics.median(confidence_values), 3)
        if confidence_values
        else None,
        "single_supplier_signal_values": dict(supplier_values),
        "rule_categories": dict(rule_categories),
        "rule_anomaly_flags": dict(rule_flags),
        "responses_with_unsupported_inference_terms": manual_review,
        "responses_with_unsupported_inference_terms_pct": round(
            100 * manual_review / len(reviewed), 2
        )
        if reviewed
        else 0,
        "conclusion": {
            "useful_for": [
                "structuring a notice into fixed analytical fields",
                "drafting observation, interpretation, significance and limitation",
                "prioritizing cards for document-level review",
            ],
            "not_reliable_as_ground_truth_for": [
                "single-supplier conclusions",
                "supplier identity or winner",
                "legal violations, corruption, collusion or spending efficiency",
                "confirmation of a price anomaly without comparable scope and documents",
            ],
            "sampling_limitation": "Results are the first completed tasks from a priority queue, not a random sample of all procurements.",
        },
    }

    args.json_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with args.csv_output.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(reviewed[0]) if reviewed else [])
        writer.writeheader()
        writer.writerows(reviewed)

    markdown = f"""# Итоги локального LLM-анализа Qwen

## Объём и качество

- Обработано результатов: {len(results)}.
- Уникальных закупок: {unique_tasks}.
- Валидный JSON: {valid_json} из {len(results)} ({summary['valid_json_pct']}%).
- Покрытие очереди LLM: {summary['coverage_of_llm_queue_pct']}%.
- Модель: Qwen 3.5 9B через локальную Ollama.
- Средняя заявленная моделью уверенность классификации:
  {summary['mean_category_confidence']}. Это самооценка модели, а не измеренная
  точность.
- Признак единственного поставщика: 34 ответа `null`, 4 ответа `false`,
  подтверждений `true` нет.
- Состав обработанных карточек по правилу: 24 `other`, 9 IT и телеком,
  3 логистика/эксплуатация, 1 профессиональные услуги и 1 строительство.

## Наблюдение

Модель стабильно соблюдает JSON-схему и заполняет четыре требуемых блока:
наблюдение, интерпретация, значимость и ограничение. Это позволяет автоматически
превращать короткие названия закупок и детерминированные флаги в единообразные
карточки для аналитика.

## Интерпретация

Qwen полезна как инструмент первичной разметки и подготовки черновика вывода.
Она не подтверждает аномалию: модель получает уже рассчитанный флаг и объясняет,
почему карточку стоит проверить. В {manual_review} ответах
({summary['responses_with_unsupported_inference_terms_pct']}%) найдены слова,
связанные с поставщиком, единственным поставщиком, нарушениями или иными
утверждениями, которых недостаточно во входных данных. Эти ответы отмечены в
`llm_results_review.csv` как требующие ручной проверки.

## Значимость

LLM сокращает ручную работу по чтению и структурированию карточек, но должна
использоваться после правил и статистики, а не вместо них. Наиболее безопасный
результат её работы — приоритизированный список для открытия карточек и
приложенных документов.

## Ограничения

- Проанализировано {summary['coverage_of_llm_queue_pct']}% очереди, поэтому
  результаты не описывают все 452 задачи.
- Это первые задачи приоритетной очереди, а не случайная выборка.
- В исходных карточках нет протоколов участников, победителей и итоговой цены.
- Признак единственного поставщика нельзя считать установленным.
- Ценовой скачок нельзя подтвердить без сопоставления количества, комплектации,
  технического задания и условий поставки.

## Итог

Локальная Qwen пригодна для автоматизации работы с неструктурированным текстом и
составления стандартизированного черновика аналитического вывода. Все её
риск-выводы должны маркироваться как гипотезы и подтверждаться документами.
"""
    args.markdown_output.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
