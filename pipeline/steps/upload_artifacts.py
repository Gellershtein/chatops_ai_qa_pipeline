"""
This module implements the Upload Artifacts step of the QA pipeline.
Its primary function is to collect all generated outputs from previous steps,
such as scenarios, test cases, autotests, various reports, and raw inputs,
and upload them to Minio object storage for persistent archival and access.
"""
import os
from storage.minio_client import upload
from logs.logger import log_error
from typing import Dict, Any, Union

def run(ctx: Dict[str, Any]) -> None:
    """
    Executes the Upload Artifacts step. This function iterates through all relevant
    data and files stored in the pipeline context, uploading each artifact to
    the configured Minio bucket under a directory specific to the current run ID.

    Args:
        ctx (Dict[str, Any]): The pipeline context dictionary containing paths
                              or content of all generated artifacts.
    """
    run_id = ctx["run_id"]
    bucket_name = os.getenv("MINIO_BUCKET", "qa-pipeline")

    def upload_file(file_path: str, minio_path: str) -> None:
        """
        Helper function to upload a single file from the local filesystem to Minio.

        Args:
            file_path (str): The local path to the file to be uploaded.
            minio_path (str): The destination path for the file within the Minio bucket.
        """
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    content_bytes = f.read()
                upload(bucket_name, minio_path, content_bytes)
                print(f"Uploaded file: {file_path} to Minio path: {minio_path}")
            except Exception as e:
                log_error(f"Failed to upload file {file_path} to {minio_path}: {e}")
        else:
            log_error(f"File not found for upload: {file_path}")

    def upload_content(content: Union[str, Dict[str, Any], List[Any], None], minio_path: str) -> None:
        """
        Helper function to upload string content (or JSON-serializable content) to Minio.

        Args:
            content (Union[str, Dict[str, Any], List[Any], None]): The string content or
                                                                    JSON-serializable object to be uploaded.
            minio_path (str): The destination path for the content within the Minio bucket.
        """
        if content is None:
            return
        
        # If content is a dict or list, assume it's JSON and serialize it
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, indent=2, ensure_ascii=False)
            content_bytes = content_str.encode('utf-8')
        elif isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            log_error(f"Unsupported content type for upload to {minio_path}: {type(content)}")
            return

        try:
            upload(bucket_name, minio_path, content_bytes)
            print(f"Uploaded content to Minio path: {minio_path}")
        except Exception as e:
            log_error(f"Failed to upload content to {minio_path}: {e}")

    # --- Artifact Upload Process ---

    # 1. Original Checklist (raw text)
    upload_content(ctx.get("txt"), f"{run_id}/original_checklist.txt")

    # 2. Scenarios (generated text)
    upload_content(ctx.get("scenarios"), f"{run_id}/scenarios.txt")

    # 3. Test Cases (JSON object)
    # testcases_json is already a list of dicts, so upload_content can handle it.
    upload_content(ctx.get("testcases_json"), f"{run_id}/testcases.json")

    # 4. Autotest files (individual Python files)
    for file_path in ctx.get("autotest_files", []):
        filename = os.path.basename(file_path)
        upload_file(file_path, f"{run_id}/autotests/{filename}")
    
    # Upload conftest.py if it exists
    autotests_dir = ctx.get("autotests_dir")
    if autotests_dir:
        conftest_path = os.path.join(autotests_dir, "conftest.py")
        if os.path.exists(conftest_path):
            upload_file(conftest_path, f"{run_id}/autotests/conftest.py")

    # 5. Code Quality Report (text file)
    upload_file(ctx.get("code_quality_report"), f"{run_id}/reports/code_quality_report.txt")
    
    # 6. AI Code Reviews (JSON/text files)
    for review_path in ctx.get("ai_code_reviews", []):
        filename = os.path.basename(review_path)
        upload_file(review_path, f"{run_id}/reports/{filename}")

    # 7. Test Results (XML and Log files)
    # Note: ctx.get("test_results") is not set in run_autotests.py, it sets test_results_xml
    upload_file(ctx.get("test_results_xml"), f"{run_id}/reports/test_results.xml")
    upload_file(ctx.get("test_run_log"), f"{run_id}/reports/test_run.log") # Corrected filename based on run_autotests.py
    upload_file(ctx.get("test_report_html"), f"{run_id}/reports/test_report.html") # HTML report

    # 8. QA Summary Report (text file)
    upload_file(ctx.get("qa_summary_report"), f"{run_id}/reports/qa_summary.txt")

    # 9. Bug Report (JSON file or raw text if parsing failed)
    upload_file(ctx.get("bug_report"), f"{run_id}/reports/{os.path.basename(ctx.get('bug_report', 'bug_report.json'))}")

    print(f"✅ Finished uploading all available artifacts for run_id {run_id} to Minio.")
