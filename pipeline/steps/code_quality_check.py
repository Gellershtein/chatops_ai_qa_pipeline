import subprocess
import os

def run(ctx):
    run_id = ctx["run_id"]
    report_dir = "reports"
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"code_quality_report_{run_id}.txt")

    test_dir = os.path.join("tests", "generated")

    with open(report_file, "w") as f:
        try:
            result = subprocess.run(
                ["flake8", test_dir],
                capture_output=True,
                text=True,
                check=False  # Do not raise exception on non-zero exit code
            )
            f.write(result.stdout)
            f.write(result.stderr)
        except FileNotFoundError:
            f.write("flake8 not found. Please install it with 'pip install flake8'")

    ctx["code_quality_report"] = report_file
