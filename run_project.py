import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def python():
    return str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))


def powershell(script, *arguments):
    run([
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ROOT / script),
        *arguments,
    ])


def setup():
    powershell("setup_environment.ps1")


def collect():
    executable = python()
    run([executable, "stages/stage1/scripts/collect_eis.py"])
    run([executable, "stages/stage1/scripts/collect_eis_queries.py", "--pages", "10"])
    run([
        executable,
        "stages/stage1/scripts/collect_sberbank_ast.py",
        "--all-orgs",
        "--term-mode",
        "inn",
        "--pages",
        "5",
    ])
    run([executable, "stages/stage1/scripts/probe_sources.py"])


def anonymize():
    executable = python()
    run([executable, "stages/stage1/scripts/build_stage1_dataset.py"])
    run([executable, "stages/stage1/scripts/anonymize_exports.py"])
    run([executable, "stages/stage1/scripts/audit_anonymization.py"])
    run([executable, "stages/stage1/scripts/enrich_multisource.py"])
    run([executable, "stages/stage1/scripts/summarize_stage1.py"])


def clean():
    run([python(), "stages/stage2/scripts/process_stage2.py"])


def database():
    powershell("update_database.ps1")


def analytics():
    executable = python()
    run([executable, "stages/stage3/scripts/collect_cbr_factors.py"])
    run([executable, "stages/stage3/scripts/analyze_stage3.py"])
    results = ROOT / "data" / "processed" / "stage3" / "llm_results.jsonl"
    if results.exists():
        run([executable, "stages/stage3/scripts/summarize_llm_results.py"])


def qwen():
    powershell("run_stage3_qwen.ps1", "-Limit", "25")


def report():
    run([python(), "stages/stage4/scripts/build_stage4.py"])


def notebook():
    run(["cmd.exe", "/c", str(ROOT / "open_notebook.cmd")])


ACTIONS = {
    "setup": setup,
    "collect": collect,
    "anonymize": anonymize,
    "clean": clean,
    "database": database,
    "analytics": analytics,
    "qwen": qwen,
    "report": report,
    "notebook": notebook,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    arguments = parser.parse_args()
    ACTIONS[arguments.action]()


if __name__ == "__main__":
    main()
