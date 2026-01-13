import subprocess
import os
import sys

def _run_linter(cmd: list, test_dir: str, tool_name: str) -> str:
    """Запускает один линтер и возвращает отчёт."""
    try:
        result = subprocess.run(
            cmd + [test_dir],
            capture_output=True,
            text=True,
            timeout=30  # Защита от зависаний
        )
        output = result.stdout + result.stderr
        if output.strip():
            return f"🔍 {tool_name} found issues:\n{output}\n{'-'*50}\n"
        else:
            return f"✅ {tool_name}: No issues found.\n"
    except FileNotFoundError:
        return f"⚠️ {tool_name} not installed. Skip.\n"
    except subprocess.TimeoutExpired:
        return f"⚠️ {tool_name} timed out.\n"
    except Exception as e:
        return f"⚠️ {tool_name} error: {e}\n"


def run(ctx):
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "code_quality_report.txt")

    test_dir = ctx.get("autotests_dir")
    if not test_dir or not os.path.isdir(test_dir):
        error_msg = f"ERROR: Autotests directory not found: {test_dir}"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(error_msg)
        ctx["code_quality_report"] = report_file
        return

    full_report = "🧪 Code Quality Report\n" + "="*50 + "\n\n"

    # 1. Ruff (рекомендуется как основной — быстрый и современный)
    full_report += _run_linter(
        [sys.executable, "-m", "ruff", "check", "--output-format=full"],
        test_dir,
        "Ruff"
    )

    # 2. Flake8 (для совместимости)
    full_report += _run_linter(
        [sys.executable, "-m", "flake8", "--max-line-length=120"],
        test_dir,
        "Flake8"
    )

    # 3. MyPy (проверка типов)
    full_report += _run_linter(
        [sys.executable, "-m", "mypy", "--ignore-missing-imports"],
        test_dir,
        "MyPy"
    )

    # Сохраняем полный отчёт
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(full_report)

    ctx["code_quality_report"] = report_file