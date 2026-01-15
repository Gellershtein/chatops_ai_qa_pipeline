"""
This module defines the AI QA pipeline steps and provides functionality to initialize a pipeline run.
"""
import uuid
import os
from storage.minio_client import download
from logs.logger import log_error
from pipeline.steps import (
    generate_scenarios,

    generate_testcases,
    generate_autotests,
    code_quality_check,
    ai_code_review,
    generate_qa_summary,
    generate_bug_report,
    run_autotests, pii_scan
)

# Define the sequence of pipeline steps
# Each tuple contains the step name and the function to execute for that step.
PIPELINE_STEPS = [
    ("PII Masking", pii_scan.run),
    ("Generating Scenarios", generate_scenarios.run),
    ("Generating Test Cases", generate_testcases.run),
    ("Generating Autotests", generate_autotests.run),
    ("Checking Code Quality", code_quality_check.run),
    ("Performing AI Code Review", ai_code_review.run),
    ("Running Autotests", run_autotests.run),
    ("Generating QA Summary", generate_qa_summary.run),
    ("Generating Bug Report", generate_bug_report.run)
]

def initialize_pipeline(file_name: str) -> dict:
    """
    Initializes a new pipeline run by creating a unique run ID, downloading the input file,
    and setting up the initial context for pipeline execution.

    Args:
        file_name (str): The name of the file to be processed by the pipeline.

    Returns:
        dict: A dictionary containing the initial pipeline context, including:
              - 'run_id' (str): A unique identifier for the current pipeline run.
              - 'file_name' (str): The name of the input file.
              - 'txt' (str): The content of the input file.
              - 'step_index' (int): The current step index, initialized to 0.

    Raises:
        Exception: If there is an error downloading the file or initializing the context.
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
