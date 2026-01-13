import os
import subprocess
import xmltodict
from logs.logger import log_error


def _parse_test_results(xml_path: str) -> dict:
    if not os.path.exists(xml_path):
        return {"error": "XML report not found"}

    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            data = xmltodict.parse(f.read())

        testsuite = data.get("testsuites", {}).get("testsuite")
        if not testsuite:
            testsuite = data.get("testsuite")

        if not testsuite:
            return {"error": "No testsuite found in XML"}

        if isinstance(testsuite, list):
            total_tests = sum(int(ts.get("@tests", 0)) for ts in testsuite)
            total_failures = sum(int(ts.get("@failures", 0)) for ts in testsuite)
            total_errors = sum(int(ts.get("@errors", 0)) for ts in testsuite)
            total_skipped = sum(int(ts.get("@skipped", 0)) for ts in testsuite)
        else:
            total_tests = int(testsuite.get("@tests", 0))
            total_failures = int(testsuite.get("@failures", 0))
            total_errors = int(testsuite.get("@errors", 0))
            total_skipped = int(testsuite.get("@skipped", 0))

        passed = total_tests - total_failures - total_errors - total_skipped
        return {
            "total": total_tests,
            "passed": passed,
            "failed": total_failures,
            "errors": total_errors,
            "skipped": total_skipped
        }

    except Exception as e:
        return {"error": f"Failed to parse XML: {e}"}


def run(ctx):
    run_id = ctx["run_id"]
    test_dir = ctx.get("autotests_dir")
    if not test_dir or not os.path.isdir(test_dir):
        error_msg = f"Autotests directory not found: {test_dir}"
        log_error(error_msg)
        raise FileNotFoundError(error_msg)

    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)

    xml_report = os.path.join(report_dir, "test_results.xml")
    html_report = os.path.join(report_dir, "test_report.html")
    log_file = os.path.join(report_dir, "test_run.log")

    try:
        # Запускаем pytest
        result = subprocess.run(
            [
                "pytest",
                test_dir,
                f"--junitxml={xml_report}",
                f"--html={html_report}",
                "--self-contained-html",
                "-v"
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd="/app"
        )

        # Сохраняем лог выполнения
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n=== STDERR ===\n")
            f.write(result.stderr)
            f.write(f"\n=== EXIT CODE ===\n{result.returncode}\n")

        # Парсим XML (обязательно)
        summary = _parse_test_results(xml_report)
        ctx["test_summary"] = summary

        # Сохраняем пути — даже если HTML не создан
        ctx["test_results_xml"] = xml_report
        ctx["test_run_log"] = log_file

        # Проверяем, создан ли HTML
        if os.path.exists(html_report):
            ctx["test_report_html"] = html_report
        else:
            log_error("HTML report was not generated. Check if 'pytest-html' is installed.")
            ctx["test_report_html"] = None

        print(f"✅ Autotests completed. Summary: {summary}")

    except FileNotFoundError:
        error_msg = "pytest not found. Install it via 'pip install pytest pytest-html'"
        log_error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        log_error(f"Failed to run autotests: {e}")
        raise