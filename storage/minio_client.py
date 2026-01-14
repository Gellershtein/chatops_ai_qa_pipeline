import json
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from config import config
from utils.exceptions import StorageError

client = Minio(
    config.minio_endpoint,
    access_key=config.minio_access_key,
    secret_key=config.minio_secret_key,
    secure=config.minio_secure
)

def upload(bucket, path, content: bytes):
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        client.put_object(bucket, path, data=BytesIO(content), length=len(content))
    except S3Error as e:
        raise StorageError(f"Failed to upload to Minio: {e}") from e


def download(bucket, path):
    try:
        response = client.get_object(bucket, path)
        return response.read().decode()
    except S3Error as e:
        raise StorageError(f"Failed to download from Minio: {e}") from e

def upload_json(bucket, path, data_dict):
    """Uploads a dictionary as a JSON file to MinIO."""
    json_bytes = json.dumps(data_dict, ensure_ascii=False, indent=2).encode('utf-8')
    upload(bucket, path, json_bytes)

def download_json(bucket, path):
    """Downloads a JSON file from MinIO and returns it as a dictionary."""
    content = download(bucket, path)
    return json.loads(content)