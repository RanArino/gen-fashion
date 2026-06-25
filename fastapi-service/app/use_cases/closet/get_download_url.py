from app.ports import ImageStoragePort


class GetDownloadUrlUseCase:
    """Use case for getting a signed download URL for the caller's own object."""

    def __init__(self, image_storage: ImageStoragePort):
        self.image_storage = image_storage

    async def execute(self, user_id: str, item_id: str) -> str:
        return await self.image_storage.get_signed_download_url(user_id, item_id)
