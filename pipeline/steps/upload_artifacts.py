
import os
from storage.minio_client import upload
from logs.logger import log_error

def run(ctx):
    run_id = ctx["run_id"]
    bucket_name = os.getenv("MINIO_BUCKET", "qa-pipeline")

    def upload_file(file_path, minio_path):
        """Helper to upload a single file."""
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    content_bytes = f.read()
                upload(bucket_name, minio_path, content_bytes)
            except Exception as e:
                log_error(f"Failed to upload {file_path} to {minio_path}: {e}")

    def upload_content(content_str, minio_path):
        """Helper to upload string content."""
        if content_str:
            try:
                upload(bucket_name, minio_path, content_str.encode('utf-8'))
            except Exception as e:
                log_error(f"Failed to upload content to {minio_path}: {e}")

    # 1. Original Checklist
    upload_content(ctx.get("txt"), f"{run_id}/checklist.txt")

    # 2. Scenarios
    upload_content(ctx.get("scenarios"), f"{run_id}/scenarios.txt")

    # 3. Test Cases JSON
    upload_content(ctx.get("testcases_json"), f"{run_id}/testcases.json")

    # 4. Autotest files
    for file_path in ctx.get("autotest_files", []):
        filename = os.path.basename(file_path)
        upload_file(file_path, f"{run_id}/autotests/{filename}")
        
    # 5. Code Quality Report
    upload_file(ctx.get("code_quality_report"), f"{run_id}/reports/code_quality_report.txt")
    
    # 6. AI Code Reviews
    for review_path in ctx.get("ai_code_reviews", []):
        filename = os.path.basename(review_path)
        upload_file(review_path, f"{run_id}/reports/{filename}")

    # 7. Test Results (XML and Log)
    upload_file(ctx.get("test_results"), f"{run_id}/reports/test_results.xml")
    upload_file(ctx.get("test_run_log"), f"{run_id}/reports/test_run_log.txt")

    # 8. QA Summary Report
    upload_file(ctx.get("qa_summary_report"), f"{run_id}/reports/qa_summary.txt")

    # 9. Bug Report
    upload_file(ctx.get("bug_report"), f"{run_id}/reports/bug_report.json")

    print(f"Finished uploading artifacts for run_id {run_id}")
