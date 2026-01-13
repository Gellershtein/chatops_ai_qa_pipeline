import os
import subprocess
from logs.logger import log_error

def run(ctx):
    """
    Simulates getting test results by running pytest on the generated tests.
    """
    run_id = ctx["run_id"]
    test_dir = os.path.join("tests", "generated")
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    
    results_file_xml = os.path.join(report_dir, f"test_results_{run_id}.xml")

    if not os.path.exists(test_dir):
        log_error(f"Test directory {test_dir} not found for running tests.")
        ctx["test_results"] = None
        return

    try:
        # Run pytest and capture output
        # Using --junitxml to get a structured report
        result = subprocess.run(
            ["pytest", test_dir, f"--junitxml={results_file_xml}"],
            capture_output=True,
            text=True,
            check=False # We don't want to fail the pipeline if tests fail
        )
        
        # The XML file is the primary artifact, but we can also save the stdout/stderr
        results_file_log = os.path.join(report_dir, f"test_run_log_{run_id}.txt")
        with open(results_file_log, "w") as f:
            f.write("--- STDOUT ---\n")
            f.write(result.stdout)
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)

        print(f"Pytest run completed. Report saved to {results_file_xml}")
        ctx["test_results"] = results_file_xml # The main artifact is the XML report
        ctx["test_run_log"] = results_file_log

    except FileNotFoundError:
        error_message = "pytest not found. Please install it with 'pip install pytest'"
        log_error(error_message)
        raise Exception(error_message)
