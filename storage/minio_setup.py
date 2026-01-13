import os
import time
from minio import Minio
from minio.error import S3Error

# It's good practice to add retry logic for service dependencies.
MAX_RETRIES = 10
RETRY_DELAY = 5 # seconds

def main():
    bucket_name = os.getenv("MINIO_BUCKET", "qa-pipeline")
    
    secure_str = os.getenv("MINIO_SECURE", "false").lower()
    secure = secure_str == "true"

    client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=secure
    )

    # Wait for Minio to be ready
    print("Connecting to Minio...")
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # The health check in minio-py is not straightforward,
            # so we'll just try a simple operation like listing buckets.
            client.list_buckets()
            print("Successfully connected to Minio.")
            break
        except Exception as e:
            retries += 1
            print(f"Waiting for Minio to be ready... (Attempt {retries}/{MAX_RETRIES})")
            if retries >= MAX_RETRIES:
                print(f"Error: Could not connect to Minio after {MAX_RETRIES} attempts. {e}")
                exit(1)
            time.sleep(RETRY_DELAY)


    # Check if the bucket exists and create it if not
    try:
        if not client.bucket_exists(bucket_name):
            print(f"Bucket '{bucket_name}' not found. Creating it...")
            client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
        else:
            print(f"Bucket '{bucket_name}' already exists.")
    except S3Error as e:
        print(f"Error interacting with bucket: {e}")
        exit(1)

if __name__ == "__main__":
    main()
