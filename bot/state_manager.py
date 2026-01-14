import os
from collections import defaultdict
from storage.minio_client import upload_json, download_json
from logs.logger import log_error
from models.requirement import Requirement

# In-memory state management.
# In a production environment, this should be replaced with a persistent storage like Redis or a database.
pipeline_runs = {}
step_retry_counts = defaultdict(lambda: defaultdict(int))

def get_context_minio_path(run_id: str) -> str:
    """
    Get the path to the context file in MinIO.

    Args:
        run_id: The ID of the pipeline run.

    Returns:
        The path to the context file.
    """
    return f"contexts/{run_id}/context.json"


def save_context_to_minio(ctx: dict):
    """
    Saves the pipeline context to MinIO as a JSON file.

    Args:
        ctx: The pipeline context.
    """
    run_id = ctx["run_id"]
    serializable_ctx = ctx.copy()
    if "requirements" in serializable_ctx and isinstance(serializable_ctx["requirements"], list):
        serializable_ctx["requirements"] = [req.__dict__ for req in serializable_ctx["requirements"]]
    upload_json(os.getenv("MINIO_BUCKET"), get_context_minio_path(run_id), serializable_ctx)


def load_context_from_minio(run_id: str) -> dict:
    """
    Loads the pipeline context from MinIO.

    Args:
        run_id: The ID of the pipeline run.

    Returns:
        The pipeline context.
    """
    loaded_ctx = download_json(os.getenv("MINIO_BUCKET"), get_context_minio_path(run_id))
    if "requirements" in loaded_ctx and isinstance(loaded_ctx["requirements"], list):
        loaded_ctx["requirements"] = [Requirement(**req_dict) for req_dict in loaded_ctx["requirements"]]
    return loaded_ctx


def delete_context_from_minio(run_id: str):
    """
    Deletes the pipeline context from MinIO.

    Args:
        run_id: The ID of the pipeline run.
    """
    try:
        # This should be implemented to delete the context file from MinIO
        pass
    except Exception as e:
        log_error(f"Failed to delete context for run_id {run_id} from MinIO: {e}")
