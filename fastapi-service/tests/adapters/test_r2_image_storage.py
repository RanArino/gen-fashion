import pytest
from app.config import get_settings
from app.adapters.r2_image_storage import R2ImageStorage


class FakeS3Client:
    def __init__(self, endpoint_url):
        self.endpoint_url = endpoint_url
        self.deleted = []

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"{self.endpoint_url}/{Params['Bucket']}/{Params['Key']}?operation={operation}"

    def delete_object(self, Bucket, Key):
        self.deleted.append((Bucket, Key))


def fake_boto3_client(service, endpoint_url, **kwargs):
    assert service == "s3"
    return FakeS3Client(endpoint_url)


@pytest.mark.asyncio
async def test_r2_storage_uses_public_endpoint_for_signed_urls(monkeypatch):
    monkeypatch.setenv("R2_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("R2_PUBLIC_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "minioadmin")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "minioadmin")
    get_settings.cache_clear()
    monkeypatch.setattr("app.adapters.r2_image_storage.boto3.client", fake_boto3_client)

    storage = R2ImageStorage()

    upload_url = await storage.get_signed_upload_url("user-123", "item-123")
    await storage.delete_image("user-123/closet/item-123.jpg")

    assert upload_url.startswith("http://localhost:9000/gen-fashion-images/")
    assert storage._client.endpoint_url == "http://minio:9000"
    get_settings.cache_clear()
