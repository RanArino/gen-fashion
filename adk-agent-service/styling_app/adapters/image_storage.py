"""R2/MinIO image storage + image fetching for the M4 tools.

Same bucket/credential names as fastapi-service's R2ImageStorage (M2-7); the
key layout is the shared contract: {user_id}/closet/{item_id}.jpg for closet
images, __shared__/closet/{item_id}.jpg for the M3 seed, and
{user_id}/coordinates/{uuid}.jpg for generated results.
"""

from functools import lru_cache
from urllib.parse import unquote, urlparse

import boto3
import httpx
from botocore.config import Config

from ..config import get_settings


@lru_cache
def _clients() -> tuple:
    settings = get_settings()
    common = {
        "aws_access_key_id": settings.r2_access_key_id,
        "aws_secret_access_key": settings.r2_secret_access_key,
        "region_name": "auto",
        "config": Config(signature_version="s3v4"),
    }
    client = boto3.client("s3", endpoint_url=settings.r2_endpoint_url, **common)
    presign_client = boto3.client(
        "s3",
        endpoint_url=settings.r2_public_endpoint_url or settings.r2_endpoint_url,
        **common,
    )
    return client, presign_client


def get_download_url(key: str, expiration_seconds: int = 3600) -> str:
    """Presigned GET URL for an object key (browser-reachable endpoint)."""
    settings = get_settings()
    _, presign_client = _clients()
    return presign_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expiration_seconds,
    )


def put_bytes(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    """Store bytes at `key` and return a presigned download URL."""
    settings = get_settings()
    client, _ = _clients()
    client.put_object(
        Bucket=settings.r2_bucket_name, Key=key, Body=data, ContentType=content_type
    )
    return get_download_url(key)


def fetch_bytes(url_or_key: str) -> bytes:
    """Fetch image bytes from an http(s) URL or an R2/MinIO object key."""
    if url_or_key.startswith("http://") or url_or_key.startswith("https://"):
        own_key = _object_key_from_own_url(url_or_key)
        if own_key:
            return _fetch_key(own_key)
        response = httpx.get(url_or_key, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        return response.content
    return _fetch_key(url_or_key)


def _fetch_key(key: str) -> bytes:
    settings = get_settings()
    client, _ = _clients()
    obj = client.get_object(Bucket=settings.r2_bucket_name, Key=key)
    return obj["Body"].read()


def _object_key_from_own_url(url: str) -> str | None:
    settings = get_settings()
    endpoint = settings.r2_public_endpoint_url or settings.r2_endpoint_url
    if not endpoint:
        return None

    parsed_url = urlparse(url)
    parsed_endpoint = urlparse(endpoint)
    if (parsed_url.scheme, parsed_url.netloc) != (
        parsed_endpoint.scheme,
        parsed_endpoint.netloc,
    ):
        return None

    bucket_prefix = f"/{settings.r2_bucket_name}/"
    path = unquote(parsed_url.path)
    if not path.startswith(bucket_prefix):
        return None
    key = path[len(bucket_prefix) :]
    return key or None
