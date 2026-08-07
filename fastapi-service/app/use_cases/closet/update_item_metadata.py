import logging
from uuid import UUID

from app.domain.closet import (
    ClosetItemNotFound,
    ClosetOwnershipStatus,
    ClothingItemId,
    ClothingTag,
    IntentTag,
)
from app.ports import ClosetRepositoryPort, EmbeddingSearchPort


logger = logging.getLogger(__name__)


class UpdateClosetItemMetadataUseCase:
    """Update an owner's searchable metadata and mirror it to Elasticsearch."""

    def __init__(self, closet_repo: ClosetRepositoryPort, embedding_search: EmbeddingSearchPort):
        self.closet_repo = closet_repo
        self.embedding_search = embedding_search

    async def execute(
        self,
        user_id: str,
        item_id: str,
        *,
        gender: str | None = None,
        category: str | None = None,
        colors: list[str] | None = None,
        season: str | None = None,
        tags: list[str] | None = None,
        ownership_status: str | None = None,
        intent_tags: list[str] | None = None,
    ) -> dict:
        item = await self.closet_repo.get_by_id(user_id, ClothingItemId(UUID(item_id)))
        if item is None:
            raise ClosetItemNotFound(f"Closet item not found: {item_id}")
        if ownership_status is not None:
            item.set_ownership_status(ClosetOwnershipStatus(ownership_status))
        item.set_metadata(
            gender=gender,
            category=category,
            colors=colors,
            season=season,
            tags=None if tags is None else [ClothingTag(name="tag", value=value) for value in tags],
            intent_tags=None if intent_tags is None else [IntentTag(value) for value in intent_tags],
        )
        await self.closet_repo.update(item)
        try:
            await self.embedding_search.update_item_metadata(
                item_id=item_id,
                tags=[tag.value for tag in item.tags],
                category=item.category,
                colors=item.colors,
                season=item.season,
                gender=item.gender,
                ownership_status=item.ownership_status.value,
                intent_tags=[t.value for t in item.intent_tags],
            )
        except Exception:
            logger.exception("Failed to reindex closet item %s", item_id)
        return {
            "item_id": item_id,
            "status": item.status.value,
            "ownershipStatus": item.ownership_status.value,
        }
