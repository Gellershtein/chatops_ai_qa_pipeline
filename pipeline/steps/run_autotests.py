"""
This module implements the Run Autotests step of the QA pipeline.
It executes the generated Pytest autotests, captures their output,
generates XML and HTML reports, parses the XML for a summary,
and stores all relevant results and report paths in the pipeline context.
"""
import os
import subprocess
import xmltodict
from logs.logger import log_error
from typing import Dict, Any, Union, List

def _parse_test_results(xml_path: str) -> Dict[str, Union[int, str]]:
    """
    Parses a JUnit XML test report to extract a summary of test execution results.
    It counts total, passed, failed, errored, and skipped tests.

    Args:
        xml_path (str): The file path to the JUnit XML report.

    Returns:
        Dict[str, Union[int, str]]: A dictionary containing the test summary with keys like
                                    "total", "passed", "failed", "errors", "skipped".
                                    If parsing fails or the file is not found, an "error" key will be present.
    """
    if not os.path.exists(xml_path):
        return {"error": "XML report not found"}

    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            data = xmltodict.parse(f.read())

        # XML structure can vary (single <testsuite> or <testsuites> containing multiple <testsuite>)
        testsuite_data = data.get("testsuites", {}).get("testsuite")
        if not testsuite_data:
            testsuite_data = data.get("testsuite") # Direct access if only one testsuite

        if not testsuite_data:
            return {"error": "No testsuite found in XML"}

        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0

        # Aggregate results if there are multiple testsuites
        if isinstance(testsuite_data, list):
            for ts in testsuite_data:
                total_tests += int(ts.get("@tests", 0))
                total_failures += int(ts.get("@failures", 0))
                total_errors += int(ts.get("@errors", 0))
                total_skipped += int(ts.get("@skipped", 0))
        else: # Single testsuite
            total_tests = int(testsuite_data.get("@tests", 0))
            total_failures = int(testsuite_data.get("@failures", 0))
            total_errors = int(testsuite_data.get("@errors", 0))
            total_skipped = int(testsuite_data.get("@skipped", 0))

        passed = total_tests - total_failures - total_errors - total_skipped
        return {
            "total": total_tests,
            "passed": passed,
            "failed": total_failures,
            "errors": total_errors,
            "skipped": total_skipped
        }

    except Exception as e:
        log_error(f"Failed to parse XML test results from {xml_path}: {e}")
        return {"error": f"Failed to parse XML: {e}"}


def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Run Autotests step. This function orchestrates the execution of Pytest
    on the generated autotests, producing JUnit XML and HTML reports. It captures
    the full console output, parses the XML report to extract a test summary,
    and stores all relevant results and report paths in the pipeline context.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary, which must contain:
                              - 'run_id' (str): The unique identifier for the current pipeline run.
                              - 'autotests_dir' (str): The path to the directory containing the autotest files.

    Raises:
        FileNotFoundError: If the 'autotests_dir' is not found.
        RuntimeError: If `pytest` is not found in the system's PATH.
        Exception: For any other errors occurring during test execution or report processing.
    """
    run_id = ctx["run_id"]
    test_dir = ctx.get("autotests_dir")
    if not test_dir or not os.path.isdir(test_dir):
        error_msg = f"Autotests directory not found or invalid: {test_dir}. Cannot run autotests."
        log_error(error_msg)
        raise FileNotFoundError(error_msg)

    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True) # Ensure report directory exists

    xml_report_path = os.path.join(report_dir, "test_results.xml")
    html_report_path = os.path.join(report_dir, "test_report.html")
    log_file_path = os.path.join(report_dir, "test_run.log")

    try:
        # Construct the pytest command with report generation flags
        pytest_command = [
            "pytest",
            test_dir,
            f"--junitxml={xml_report_path}",      # Generate JUnit XML report
            f"--html={html_report_path}",         # Generate HTML report
            "--self-contained-html",              # Embed assets into HTML report
            "-v"                                  # Verbose output
        ]

        # Execute pytest as a subprocess
        result = subprocess.run(
            pytest_command,
            capture_output=True, # Capture stdout and stderr
            text=True,           # Decode output as text
            check=False,         # Do not raise an exception for non-zero exit codes (pytest reports failures via exit code)
            cwd="/app"           # Execute from the /app directory (Docker context)
        )

        # --- Add Run ID to Reports ---
        run_id_header = f"Run ID: {run_id}\n{'='*50}\n\n"

        # Prepend Run ID to HTML report if it was generated
        if os.path.exists(html_report_path):
            with open(html_report_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            with open(html_report_path, "w", encoding="utf-8") as f:
                f.write(run_id_header + html_content)
        else:
            log_error("HTML report was not generated. Check if 'pytest-html' is installed and working.")
            ctx["test_report_html"] = None


        # Create a comprehensive log file including stdout, stderr, and exit code
        log_content = (
            run_id_header +
            "=== STDOUT ===\n" + result.stdout +
            "\n=== STDERR ===\n" + result.stderr +
            f"\n=== EXIT CODE ===\n{result.returncode}\n"
        )
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(log_content)

        # Parse the generated JUnit XML report for summary statistics
        summary = _parse_test_results(xml_report_path)
        ctx["test_summary"] = summary # Store the summary in context

        # Store paths to generated reports in the context
        ctx["test_results_xml"] = xml_report_path
        ctx["test_run_log"] = log_file_path
        
        # Only store html report path if it actually exists
        if os.path.exists(html_report_path):
            ctx["test_report_html"] = html_report_path
        

        print(f"✅ Autotests completed. Summary: {summary}")

    except FileNotFoundError:
        error_msg = "pytest command not found. Ensure pytest is installed and accessible in the environment."
        log_error(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution or report processing
        log_error(f"Failed to run autotests: {e}")
        raise