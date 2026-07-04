"""Google Cloud Storage helper for document uploads referenced by the ingestion pipeline."""
from __future__ import annotations

import uuid
from datetime import timedelta

from google.cloud import storage

from app.core.config import get_settings

settings = get_settings()

_client: storage.Client | None = None


def get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=settings.project_id)
    return _client


def upload_bytes(data: bytes, filename: str, content_type: str = "application/pdf") -> str:
    """Upload raw bytes to GCS and return the gs:// path."""
    client = get_client()
    bucket = client.bucket(settings.gcs_bucket)
    blob_name = f"uploads/{uuid.uuid4()}-{filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)
    return f"gs://{settings.gcs_bucket}/{blob_name}"


def signed_url(gcs_path: str, expires_minutes: int = 30) -> str:
    """Generate a signed URL so the frontend can preview an uploaded document."""
    client = get_client()
    _, _, rest = gcs_path.partition("gs://")
    bucket_name, _, blob_name = rest.partition("/")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(expiration=timedelta(minutes=expires_minutes))


def download_bytes(gcs_path: str) -> bytes:
    client = get_client()
    _, _, rest = gcs_path.partition("gs://")
    bucket_name, _, blob_name = rest.partition("/")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()


def delete_blob(gcs_path: str) -> None:
    client = get_client()
    _, _, rest = gcs_path.partition("gs://")
    bucket_name, _, blob_name = rest.partition("/")
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()
