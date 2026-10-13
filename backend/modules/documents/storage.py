import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def _setting(*names: str, default: str | None = None) -> str | None:
    """Return the first set env var among ``names`` (new S3_* names preferred,
    legacy MINIO_* kept for backwards-compatibility)."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


# Bucket name is read at import (worker imports it); configurable for managed
# object stores (Cloudflare R2 / Supabase Storage / MinIO).
BUCKET_NAME = _setting("S3_BUCKET", "MINIO_BUCKET", default="prism-documents")


def get_s3_client():
    """Build an S3 client for any S3-compatible store (MinIO, Cloudflare R2,
    Supabase Storage, AWS S3).

    The endpoint scheme defaults to https for remote hosts (so pre-signed URLs
    are https and load in the browser without mixed-content errors) and http
    only for localhost dev.
    """
    endpoint = _setting("S3_ENDPOINT", "MINIO_ENDPOINT", default="localhost:9000")
    if not endpoint.startswith("http"):
        is_local = endpoint.startswith(("localhost", "127.0.0.1"))
        scheme = "http" if is_local else "https"
        endpoint = f"{scheme}://{endpoint}"

    # Path-style addressing works across MinIO and R2; some providers need
    # virtual-hosted style, so it's overridable.
    addressing_style = _setting("S3_ADDRESSING_STYLE", default="path")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_setting("S3_ACCESS_KEY", "MINIO_ACCESS_KEY", default="minioadmin"),
        aws_secret_access_key=_setting("S3_SECRET_KEY", "MINIO_SECRET_KEY", default="minioadmin"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": addressing_style},
        ),
        # R2 uses "auto"; MinIO/S3 accept any region string.
        region_name=_setting("S3_REGION", "MINIO_REGION", default="us-east-1"),
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

def delete_file(object_name: str) -> bool:
    """Delete an object from the MinIO documents bucket."""
    s3 = get_s3_client()
    try:
        s3.delete_object(Bucket=BUCKET_NAME, Key=object_name)
        return True
    except ClientError as e:
        error_code = str(e.response.get("Error", {}).get("Code"))
        if error_code in ("404", "NoSuchKey"):
            return True
        raise

def generate_presigned_url(object_name: str, expires_in: int = 3600) -> str:
    """Generate a temporary pre-signed URL to view the object in MinIO."""
    s3 = get_s3_client()
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET_NAME, "Key": object_name},
        ExpiresIn=expires_in,
    )
