
import uuid
import os
from storage.minio_client import download
from logs.logger import log_error
from pipeline.steps import (
    generate_scenarios,
    pii_scan,
    generate_testcases,
    generate_autotests,
    code_quality_check,
    ai_code_review,
    generate_qa_summary,
    generate_bug_report,
    upload_artifacts,
    run_autotests
)
from pipeline.steps.garb import trigger_ci, get_test_results

# Define the sequence of pipeline steps
PIPELINE_STEPS = [
    ("PII Masking", pii_scan.run),
    ("Generating Scenarios", generate_scenarios.run),
    ("Generating Test Cases", generate_testcases.run),
    #("Parsing Generated Test Cases", parse_json.run), # Moved parse_json here
    ("Generating Autotests", generate_autotests.run),
    ("Checking Code Quality", code_quality_check.run),
    ("Performing AI Code Review", ai_code_review.run),
    ("Running Autotests", run_autotests.run),
    ("Generating QA Summary", generate_qa_summary.run),
    ("Generating Bug Report", generate_bug_report.run),
    #("Uploading Artifacts to MinIO", upload_artifacts.run),
]

def initialize_pipeline(file_name):
    """
    Initializes the pipeline run, creating the initial context.
    """
    try:
        bucket_name = os.getenv("MINIO_BUCKET", "qa-pipeline")
        txt = download(bucket_name, file_name)
        ctx = {
            "run_id": str(uuid.uuid4()),
            "file_name": file_name,
            "txt": txt,
            "step_index": 0
        }
        return ctx
    except Exception as e:
        log_error(f"Failed to initialize pipeline for {file_name}: {e}")
        raise
