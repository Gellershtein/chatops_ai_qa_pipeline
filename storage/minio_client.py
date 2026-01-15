"""
This module provides a client for interacting with Minio object storage.
It encapsulates common operations such as uploading and downloading files,
and specifically handles JSON serialization/deserialization for context management.
"""
import os
import json
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from utils.exceptions import StorageError
from typing import Dict, Any, Union

# Initialize the Minio client using environment variables for configuration.
# These variables should be set in the .env file or the environment where the application runs.
# MINIO_ENDPOINT: The URL of the Minio server.
# MINIO_ACCESS_KEY: The access key for Minio authentication.
# MINIO_SECRET_KEY: The secret key for Minio authentication.
# MINIO_SECURE: 'True' for HTTPS connection, 'False' for HTTP.
client: Minio = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=os.getenv("MINIO_SECURE", "False").lower() == 'true' # Default to False if not explicitly 'True'
)

def upload(bucket: str, path: str, content: bytes) -> None:
    """
    Uploads raw byte content to a specified path within a Minio bucket.
    If the bucket does not exist, it will be created.

    Args:
        bucket (str): The name of the Minio bucket.
        path (str): The object path within the bucket (e.g., "folder/file.txt").
        content (bytes): The byte content to be uploaded.

    Raises:
        StorageError: If the upload operation fails due to an S3 error.
    """
    try:
        # Check if bucket exists, create if not
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        # Upload the content
        client.put_object(bucket, path, data=BytesIO(content), length=len(content))
    except S3Error as e:
        raise StorageError(f"Failed to upload to Minio bucket '{bucket}', path '{path}': {e}") from e


def download(bucket: str, path: str) -> str:
    """
    Downloads content from a specified path within a Minio bucket as a UTF-8 decoded string.

    Args:
        bucket (str): The name of the Minio bucket.
        path (str): The object path within the bucket to download.

    Returns:
        str: The decoded string content of the downloaded object.

    Raises:
        StorageError: If the download operation fails due to an S3 error or if the object does not exist.
    """
    try:
        # Get the object from Minio
        response = client.get_object(bucket, path)
        # Read and decode the content
        return response.read().decode('utf-8')
    except S3Error as e:
        raise StorageError(f"Failed to download from Minio bucket '{bucket}', path '{path}': {e}") from e

def upload_json(bucket: str, path: str, data_dict: Dict[str, Any]) -> None:
    """
    Uploads a Python dictionary as a JSON file to a specified path within a Minio bucket.
    The dictionary is serialized to a JSON string and then encoded to bytes.

    Args:
        bucket (str): The name of the Minio bucket.
        path (str): The object path within the bucket where the JSON file will be stored.
        data_dict (Dict[str, Any]): The dictionary to be serialized and uploaded.

    Raises:
        StorageError: If the upload operation fails.
    """
    json_bytes = json.dumps(data_dict, ensure_ascii=False, indent=2).encode('utf-8')
    upload(bucket, path, json_bytes)

def download_json(bucket: str, path: str) -> Dict[str, Any]:
    """
    Downloads a JSON file from a specified path within a Minio bucket and
    deserializes it into a Python dictionary.

    Args:
        bucket (str): The name of the Minio bucket.
        path (str): The object path within the bucket where the JSON file is located.

    Returns:
        Dict[str, Any]: The deserialized Python dictionary.

    Raises:
        StorageError: If the download operation fails.
        json.JSONDecodeError: If the downloaded content is not valid JSON.
    """
    content = download(bucket, path)
    return json.loads(content)