"""
This module implements the Code Quality Check step of the QA pipeline.
It integrates various Python linters (Ruff, Flake8, MyPy) to analyze auto-generated
autotest code and consolidates their reports into a single file.
"""
import subprocess
import os
import sys
from typing import List

def _run_linter(cmd: List[str], test_dir: str, tool_name: str) -> str:
    """
    Executes a single code linter command on the specified directory and captures its output.

    Args:
        cmd (List[str]): A list representing the linter command and its arguments (e.g., ["ruff", "check"]).
        test_dir (str): The path to the directory containing the code to be linted.
        tool_name (str): The name of the linting tool (e.g., "Ruff", "Flake8").

    Returns:
        str: A formatted string containing the linter's output or a status message.
             Includes error messages if the tool is not found, times out, or encounters other exceptions.
    """
    try:
        # Run the linter command as a subprocess
        result = subprocess.run(
            cmd + [test_dir], # Append the target directory to the command
            capture_output=True, # Capture stdout and stderr
            text=True,           # Decode stdout/stderr as text
            timeout=30           # Timeout to prevent hanging processes
        )
        output = result.stdout + result.stderr # Combine stdout and stderr
        
        # Format the output based on whether issues were found
        if output.strip():
            return f"🔍 {tool_name} found issues:\n{output}\n{'-'*50}\n"
        else:
            return f"✅ {tool_name}: No issues found.\n"
    except FileNotFoundError:
        return f"⚠️ {tool_name} not installed or not found in PATH. Skipping.\n"
    except subprocess.TimeoutExpired:
        # If the linter times out, terminate the process and report
        return f"⚠️ {tool_name} timed out after 30 seconds. Skipping.\n"
    except Exception as e:
        # Catch any other unexpected errors during linter execution
        return f"⚠️ {tool_name} error: {e}\n"


def run(ctx: dict) -> None:
    """
    Executes the Code Quality Check step. It runs a series of Python linters
    (Ruff, Flake8, MyPy) on the autotests generated in a previous step.
    The output from each linter is collected, consolidated into a single report file,
    and the path to this report is stored in the pipeline context.

    Args:
        ctx (dict): The pipeline context dictionary, which must contain:
                    - 'run_id' (str): The unique identifier for the current pipeline run.
                    - 'autotests_dir' (str): The path to the directory containing the autotest files.
    """
    run_id = ctx["run_id"]
    report_dir = os.path.join("artifacts", run_id, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "code_quality_report.txt")

    test_dir = ctx.get("autotests_dir")
    if not test_dir or not os.path.isdir(test_dir):
        error_msg = f"ERROR: Autotests directory not found or invalid: {test_dir}. Skipping code quality check."
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(error_msg)
        ctx["code_quality_report"] = report_file
        print(error_msg)
        return

    full_report = "🧪 Code Quality Report\n" + "="*50 + "\n\n"

    # 1. Run Ruff (recommended as primary due to speed and modern features)
    full_report += _run_linter(
        [sys.executable, "-m", "ruff", "check", "--output-format=full"],
        test_dir,
        "Ruff"
    )

    # 2. Run Flake8 (for broader compatibility and additional checks)
    full_report += _run_linter(
        [sys.executable, "-m", "flake8", "--max-line-length=120"],
        test_dir,
        "Flake8"
    )

    # 3. Run MyPy (for static type checking)
    full_report += _run_linter(
        [sys.executable, "-m", "mypy", "--ignore-missing-imports"],
        test_dir,
        "MyPy"
    )

    # Save the consolidated full report to a file
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(full_report)

    ctx["code_quality_report"] = report_file
    print(f"✅ Code Quality Check completed. Report saved to {report_file}")