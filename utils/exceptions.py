"""
This module defines custom exception classes used throughout the ChatOps AI QA Pipeline.
These exceptions provide more specific error handling and identification for different
failure domains within the application, such as storage, LLM interactions, and pipeline execution.
"""

class StorageError(Exception):
    """Custom exception raised for errors related to storage operations (e.g., Minio)."""
    pass

class LLMError(Exception):
    """Custom exception raised for errors related to Large Language Model (LLM) interactions."""
    pass

class PipelineError(Exception):
    """Custom exception raised for errors occurring during the AI QA pipeline execution."""
    pass
