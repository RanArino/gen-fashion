from app.ports import ImageStoragePort


class R2ImageStorage(ImageStoragePort):
    """Cloudflare R2 adapter for image storage (M2-7)."""

    async def get_signed_upload_url(
        self, user_id: str, item_id: str, expiration_seconds: int = 900
    ) -> str:
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    async def get_download_url(self, image_path: str) -> str:
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    async def delete_image(self, image_path: str) -> None:
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")

    async def verify_image_exists(self, image_path: str) -> bool:
        raise NotImplementedError("Implement in M2-7: Cloudflare R2 adapter")
