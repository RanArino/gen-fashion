import logging
from uuid import UUID
from app.domain.closet import ClosetItemNotFound, ClothingItemId
from app.ports import ClosetRepositoryPort, ImageStoragePort, EmbeddingSearchPort


logger = logging.getLogger(__name__)


class DeleteClosetItemUseCase:
    """Use case for deleting a closet item (M2-6)."""

    def __init__(
        self,
        closet_repo: ClosetRepositoryPort,
        image_storage: ImageStoragePort,
        embedding_search: EmbeddingSearchPort,
    ):
        self.closet_repo = closet_repo
        self.image_storage = image_storage
        self.embedding_search = embedding_search

    async def execute(self, user_id: str, item_id: str) -> None:
        clothing_item_id = ClothingItemId(UUID(item_id))
        item = await self.closet_repo.get_by_id(user_id, clothing_item_id)
        if item is None:
            raise ClosetItemNotFound(f"Closet item not found: {item_id}")
        try:
            await self.embedding_search.delete_item(item_id, user_id)
        except Exception:
            logger.exception("Failed to delete closet item %s from Elasticsearch", item_id)
        try:
            await self.image_storage.delete_image(item.image_url)
        except Exception:
            logger.exception("Failed to delete closet item %s from image storage", item_id)
        await self.closet_repo.delete(user_id, clothing_item_id)
