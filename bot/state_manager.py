"""
This module handles the in-memory and Minio-based state management for the AI QA pipeline runs.
It stores temporary pipeline execution data and context, allowing for state persistence across steps.
"""
import os
from collections import defaultdict
from storage.minio_client import upload_json, download_json
from logs.logger import log_error
from models.requirement import Requirement

# In-memory state management for active pipeline runs.
# Stores chat_id -> run_id mapping for quick access.
# In a production environment, this should be replaced with a persistent storage like Redis or a database.
pipeline_runs: dict[int, str] = {}

# In-memory storage for step retry counts.
# Stores chat_id -> step_name -> retry_count.
# This helps in implementing exponential backoff for failed steps.
# In a production environment, this should also be replaced with a persistent storage.
step_retry_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

def get_context_minio_path(run_id: str) -> str:
    """
    Constructs the Minio object path for a given pipeline run's context file.
    The context files are stored under a 'contexts/{run_id}/context.json' structure.

    Args:
        run_id (str): The unique identifier of the pipeline run.

    Returns:
        str: The full path where the context file is expected to be stored in Minio.
    """
    return f"contexts/{run_id}/context.json"


def save_context_to_minio(ctx: dict) -> None:
    """
    Saves the pipeline context dictionary to Minio as a JSON file.
    This function handles the serialization of 'Requirement' objects within the context
    to a dictionary format before saving.

    Args:
        ctx (dict): The pipeline context dictionary to be saved.
    """
    run_id = ctx["run_id"]
    serializable_ctx = ctx.copy()
    # If the context contains Requirement objects, convert them to dictionaries for serialization
    if "requirements" in serializable_ctx and isinstance(serializable_ctx["requirements"], list):
        serializable_ctx["requirements"] = [req.__dict__ for req in serializable_ctx["requirements"]]
    upload_json(os.getenv("MINIO_BUCKET"), get_context_minio_path(run_id), serializable_ctx)


def load_context_from_minio(run_id: str) -> dict:
    """
    Loads the pipeline context dictionary from Minio and reconstructs 'Requirement' objects.
    This function retrieves the JSON context file from Minio and converts any dictionary
    representations of requirements back into `Requirement` objects.

    Args:
        run_id (str): The unique identifier of the pipeline run.

    Returns:
        dict: The loaded pipeline context dictionary with 'Requirement' objects reconstructed.
    """
    loaded_ctx = download_json(os.getenv("MINIO_BUCKET"), get_context_minio_path(run_id))
    # If the loaded context contains dictionaries for requirements, convert them back to Requirement objects
    if "requirements" in loaded_ctx and isinstance(loaded_ctx["requirements"], list):
        loaded_ctx["requirements"] = [Requirement(**req_dict) for req_dict in loaded_ctx["requirements"]]
    return loaded_ctx


def delete_context_from_minio(run_id: str) -> None:
    """
    Deletes the pipeline context file associated with a specific run_id from Minio.

    Note: The actual implementation for deleting the object from Minio is currently
    a placeholder and needs to be added.

    Args:
        run_id (str): The unique identifier of the pipeline run whose context needs to be deleted.
    """
    try:
        # TODO: Implement actual deletion of the context file from Minio.
        # This would typically involve calling a Minio client method to remove the object.
        pass
    except Exception as e:
        log_error(f"Failed to delete context for run_id {run_id} from MinIO: {e}")
