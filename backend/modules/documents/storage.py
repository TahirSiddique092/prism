import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

BUCKET_NAME = "prism-documents"

def get_s3_client():
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    if not endpoint.startswith("http"):
        endpoint = f"http://{endpoint}"
        
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1" # MinIO usually requires a region string
    )

def ensure_bucket_exists():
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
    except ClientError as e:
        error_code = str(e.response.get("Error", {}).get("Code"))
        if error_code == "404":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            raise

def upload_file(file_obj, object_name: str, content_type: str = "application/pdf"):
    """Upload a file-like object to MinIO."""
    s3 = get_s3_client()
    s3.upload_fileobj(
        file_obj, 
        BUCKET_NAME, 
        object_name,
        ExtraArgs={"ContentType": content_type}
    )
    return object_name
