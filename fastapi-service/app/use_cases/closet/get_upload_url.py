from app.config import get_settings
from app.domain.closet import MaxClosetItemsExceeded
from app.ports import ClosetRepositoryPort, ImageStoragePort


class GetUploadUrlUseCase:
    """Use case for getting a signed upload URL (M2-3)."""

    def __init__(self, closet_repo: ClosetRepositoryPort, image_storage: ImageStoragePort):
        self.closet_repo = closet_repo
        self.image_storage = image_storage

    async def execute(self, user_id: str, item_id: str) -> str:
        count = await self.closet_repo.count_by_user(user_id)
        if count >= get_settings().max_closet_images_per_user:
            raise MaxClosetItemsExceeded("Maximum closet item count reached")
        return await self.image_storage.get_signed_upload_url(user_id, item_id)
