from app.ports import ImageStoragePort


class GetUploadUrlUseCase:
    """Use case for getting a signed upload URL (M2-3)."""

    def __init__(self, image_storage: ImageStoragePort):
        self.image_storage = image_storage

    async def execute(self, user_id: str, item_id: str) -> str:
        raise NotImplementedError("Implement in M2-3: Get upload URL")
