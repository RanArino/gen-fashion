import logging
from datetime import datetime
from uuid import UUID
from app.config import get_settings
from app.domain.closet import ClothingItemId, ClothingTag
from app.domain.closet.value_objects import ImageEmbedding
from app.ports import (
    ClosetRepositoryPort,
    EmbeddingSearchPort,
    GeminiAnalysisPort,
    ImageStoragePort,
)


logger = logging.getLogger(__name__)


def _embedding_text(analysis) -> str:
    """Build the text embedded for vector search from the analysis result.

    The search query is a natural-language description, so the indexed vector
    must come from text in the same embedding space (not the raw image).
    """
    parts = [
        analysis.category or "",
        " ".join(analysis.colors or []),
        " ".join(analysis.tags or []),
        analysis.season or "",
        analysis.style or "",
    ]
    return ". ".join(part for part in parts if part)


class ProcessUploadedClothingItemUseCase:
    """Use case for processing uploaded item (analysis + embedding) (M2-5)."""

    def __init__(
        self,
        closet_repo: ClosetRepositoryPort,
        embedding_search: EmbeddingSearchPort,
        image_storage: ImageStoragePort,
        gemini: GeminiAnalysisPort,
    ):
        self.closet_repo = closet_repo
        self.embedding_search = embedding_search
        self.image_storage = image_storage
        self.gemini = gemini

    async def execute(self, user_id: str, item_id: str) -> None:
        clothing_item_id = ClothingItemId(UUID(item_id))
        image_path = f"{user_id}/closet/{item_id}.jpg"
        try:
            image_bytes = await self.image_storage.get_image_bytes(image_path)
            analysis = await self.gemini.analyze(image_bytes)
        except Exception:
            item = await self.closet_repo.get_by_id(user_id, clothing_item_id)
            if item is not None:
                item.mark_error()
                await self.closet_repo.update(item)
            raise

        embedding_vector = None
        embedding = None
        try:
            embedding_vector = await self.gemini.embed_text(_embedding_text(analysis))
            embedding = ImageEmbedding(
                vector=embedding_vector,
                model=get_settings().embedding_model,
                created_at=datetime.utcnow().isoformat(),
            )
        except Exception:
            logger.exception("Embedding generation failed for closet item %s", item_id)

        item = await self.closet_repo.get_by_id(user_id, clothing_item_id)
        if item is None:
            return
        tags = [ClothingTag(name="tag", value=value) for value in analysis.tags]
        item.mark_ready(
            category=analysis.category,
            colors=analysis.colors,
            season=analysis.season,
            tags=tags,
            embedding=embedding,
        )
        await self.closet_repo.update(item)
        await self.embedding_search.index_item(
            item_id=item_id,
            user_id=user_id,
            is_shared=False,
            tags=analysis.tags,
            category=analysis.category,
            colors=analysis.colors,
            season=analysis.season,
            embedding=embedding_vector,
        )
