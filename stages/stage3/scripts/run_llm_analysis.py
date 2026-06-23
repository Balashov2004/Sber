from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TASKS = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_tasks.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "stage3" / "llm_results.jsonl"

SYSTEM_INSTRUCTION = """You analyze Russian procurement notices.
Return only valid JSON matching expected_output.
Do not invent participants, winners, contract values, or facts absent from input.
Do not infer the supplier, procurement law, violation, corruption, collusion or inefficient spending.
Do not describe an anomaly flag as a confirmed fact.
If the input has only a title, amount and rule flag, explicitly state that document verification is required.
Separate observation from interpretation.
Use null when evidence is unavailable.
Treat rule-based anomaly flags as hints requiring validation.
Write observation, interpretation, significance and limitation in Russian."""


def post_json(url: str, payload: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def call_openai(api_key: str, model: str, task: dict[str, object]) -> tuple[dict[str, object], str]:
    payload = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTION,
        "input": json.dumps(task, ensure_ascii=False),
    }
    response = post_json(
        "https://api.openai.com/v1/responses",
        payload,
        {"Authorization": f"Bearer {api_key}"},
    )
    return response, extract_openai_text(response)


def call_ollama(base_url: str, model: str, task: dict[str, object]) -> tuple[dict[str, object], str]:
    response = post_json(
        f"{base_url.rstrip('/')}/api/chat",
        {
            "model": model,
            "stream": False,
            "format": "json",
            "think": False,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": json.dumps(task, ensure_ascii=False)},
            ],
            "options": {
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        },
    )
    message = response.get("message", {})
    output_text = str(message.get("content", "")) if isinstance(message, dict) else ""
    return response, output_text


def extract_openai_text(response: dict[str, object]) -> str:
    texts = []
    for output in response.get("output", []):
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                texts.append(str(content.get("text", "")))
    return "\n".join(texts)


def existing_task_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    result = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("task_id"):
            result.add(str(record["task_id"]))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM enrichment for Stage 3.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--provider", choices=("ollama", "openai"), default=os.getenv("LLM_PROVIDER", "ollama"))
    parser.add_argument("--model")
    parser.add_argument("--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    tasks = [
        json.loads(line)
        for line in args.tasks.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not args.execute:
        print(f"Prepared {len(tasks)} LLM tasks. Add --execute to call the API.")
        return

    model = args.model or (
        os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        if args.provider == "ollama"
        else os.getenv("OPENAI_MODEL", "gpt-5-mini")
    )
    api_key = os.getenv("OPENAI_API_KEY", "")
    if args.provider == "openai" and not api_key:
        raise SystemExit("OPENAI_API_KEY is required for the OpenAI provider.")

    completed = existing_task_ids(args.output) if args.resume else set()
    selected = [task for task in tasks if str(task["task_id"]) not in completed][: args.limit]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume else "w"

    with args.output.open(mode, encoding="utf-8") as fh:
        for index, task in enumerate(selected, start=1):
            try:
                if args.provider == "ollama":
                    response, output_text = call_ollama(args.base_url, model, task)
                else:
                    response, output_text = call_openai(api_key, model, task)
                try:
                    structured_output = json.loads(output_text)
                    parse_status = "valid_json"
                except json.JSONDecodeError:
                    structured_output = None
                    parse_status = "invalid_json"
                record = {
                    "task_id": task["task_id"],
                    "provider": args.provider,
                    "model": model,
                    "response_id": response.get("id"),
                    "parse_status": parse_status,
                    "structured_output": structured_output,
                    "output_text": output_text,
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                fh.flush()
                print(f"Completed {index}/{len(selected)}: {task['task_id']} ({parse_status})")
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                raise SystemExit(f"LLM HTTP {exc.code}: {error_body[:800]}") from exc
            except urllib.error.URLError as exc:
                if args.provider == "ollama":
                    raise SystemExit(
                        "Ollama is unavailable. Install Ollama, start it and run: ollama pull qwen3.5:9b"
                    ) from exc
                raise
            if index < len(selected):
                time.sleep(0.2)

    print(f"Saved {len(selected)} LLM results to {args.output}")


if __name__ == "__main__":
    main()
