import json
from minio import Minio
import os
from io import BytesIO

from minio import Minio
import os
from io import BytesIO

secure_str = os.getenv("MINIO_SECURE", "false").lower()
secure = secure_str == "true"

client = Minio(
    os.getenv("MINIO_ENDPOINT"),
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=secure
)


def upload(bucket, path, content: bytes):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    client.put_object(bucket, path, data=BytesIO(content), length=len(content))

def download(bucket, path):
    response = client.get_object(bucket, path)
    return response.read().decode()

def upload_json(bucket, path, data_dict):
    """Uploads a dictionary as a JSON file to MinIO."""
    json_bytes = json.dumps(data_dict, ensure_ascii=False, indent=2).encode('utf-8')
    upload(bucket, path, json_bytes)

def download_json(bucket, path):
    """Downloads a JSON file from MinIO and returns it as a dictionary."""
    content = download(bucket, path)
    return json.loads(content)