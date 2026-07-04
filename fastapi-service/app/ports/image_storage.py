from abc import ABC, abstractmethod
class ImageStoragePort(ABC):
    """Port for image storage operations (upload, fetch, delete)."""

    @abstractmethod
    async def get_signed_upload_url(
        self, user_id: str, item_id: str, expiration_seconds: int = 900
    ) -> str:
        """
        Generate a signed URL for direct client uploads.
        Typically used for R2 or S3 signed PUTs.
        """
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def get_download_url(self, image_path: str) -> str:
        """Get a URL to download/view an image."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def get_signed_download_url(
        self, user_id: str, item_id: str, expiration_seconds: int = 3600
    ) -> str:
        """Generate a signed GET URL for the caller's own object."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def delete_image(self, image_path: str) -> None:
        """Delete an image from storage."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def verify_image_exists(self, image_path: str) -> bool:
        """Check if an image exists in storage."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def get_image_bytes(self, image_path: str) -> bytes:
        """Fetch image bytes from storage for asynchronous processing."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    @abstractmethod
    async def put_image_bytes(
        self, image_path: str, data: bytes, content_type: str = "image/jpeg"
    ) -> None:
        """Write image bytes server-side (MK-6 suggestion import)."""
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")
