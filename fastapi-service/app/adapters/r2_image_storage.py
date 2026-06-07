import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.config import get_settings
from app.ports import ImageStoragePort


class R2ImageStorage(ImageStoragePort):
    """Cloudflare R2 adapter for image storage (M2-7)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.r2_bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=settings.r2_public_endpoint_url or settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    @staticmethod
    def image_path_for(user_id: str, item_id: str) -> str:
        return f"{user_id}/closet/{item_id}.jpg"

    async def get_signed_upload_url(
        self, user_id: str, item_id: str, expiration_seconds: int = 900
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": self.image_path_for(user_id, item_id),
                "ContentType": "image/jpeg",
            },
            ExpiresIn=expiration_seconds,
        )

    async def get_download_url(self, image_path: str) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": image_path},
            ExpiresIn=3600,
        )

    async def get_signed_download_url(
        self, user_id: str, item_id: str, expiration_seconds: int = 3600
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": self.image_path_for(user_id, item_id),
            },
            ExpiresIn=expiration_seconds,
        )

    async def delete_image(self, image_path: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=image_path)

    async def verify_image_exists(self, image_path: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=image_path)
            return True
        except ClientError:
            return False

    async def get_image_bytes(self, image_path: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=image_path)
        return response["Body"].read()
