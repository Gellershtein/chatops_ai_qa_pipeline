"""
This module provides a setup script for the Minio object storage.
It ensures that the application can connect to the Minio server and that
the default bucket required for artifact storage exists, with retry logic for robustness.
"""
import os
import time
from minio import Minio
from minio.error import S3Error

# Maximum number of attempts to connect to Minio before giving up.
MAX_RETRIES = 10
# Delay in seconds between connection retry attempts.
RETRY_DELAY = 5 # seconds

def main() -> None:
    """
    Initializes the Minio client, waits for the Minio server to become available,
    and ensures that the configured bucket exists. If the bucket does not exist,
    it attempts to create it. Exits with an error if connection or bucket creation fails.
    """
    bucket_name = os.getenv("MINIO_BUCKET", "qa-pipeline")
    
    # Determine if secure (HTTPS) connection is required based on environment variable
    secure_str = os.getenv("MINIO_SECURE", "false").lower()
    secure = secure_str == "true"

    # Initialize Minio client
    client = Minio(
        os.getenv("MINIO_ENDPOINT"),
        access_key=os.getenv("MINIO_ACCESS_KEY"),
        secret_key=os.getenv("MINIO_SECRET_KEY"),
        secure=secure
    )

    # --- Connection Retry Logic ---
    print("Connecting to Minio...")
    retries = 0
    while retries < MAX_RETRIES:
        try:
            # Perform a simple operation to check connectivity (e.g., list buckets)
            client.list_buckets()
            print("Successfully connected to Minio.")
            break # Exit loop if connection is successful
        except Exception as e:
            retries += 1
            print(f"Waiting for Minio to be ready... (Attempt {retries}/{MAX_RETRIES})")
            if retries >= MAX_RETRIES:
                print(f"Error: Could not connect to Minio after {MAX_RETRIES} attempts. {e}")
                exit(1) # Exit with error code if max retries reached
            time.sleep(RETRY_DELAY) # Wait before retrying

    # --- Bucket Creation/Verification ---
    try:
        if not client.bucket_exists(bucket_name):
            print(f"Bucket '{bucket_name}' not found. Creating it...")
            client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")
        else:
            print(f"Bucket '{bucket_name}' already exists.")
    except S3Error as e:
        print(f"Error interacting with bucket '{bucket_name}': {e}")
        exit(1) # Exit with error code if bucket operation fails

if __name__ == "__main__":
    # Ensures that main() is called only when the script is executed directly
    main()
