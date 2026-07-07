import logging
from typing import Awaitable, Callable
from uuid import UUID, uuid4

import httpx

from app.config import get_settings
from app.domain.closet import (
    ClosetOwnershipStatus,
    ClothingItem,
    ClothingItemId,
    ClothingItemStatus,
    ClothingTag,
    MaxClosetItemsExceeded,
)
from app.domain.styling import StyleSessionId, StyleSessionNotFound
from app.ports import (
    ClosetRepositoryPort,
    EmbeddingSearchPort,
    ImageStoragePort,
    StylingRepositoryPort,
)


logger = logging.getLogger(__name__)

_DOWNLOAD_TIMEOUT_SECONDS = 20


async def _fetch_external_image(image_url: str) -> bytes:
    async with httpx.AsyncClient(
        timeout=_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
    ) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        return response.content


class ImportSuggestedClosetItemUseCase:
    """Save a proposed Rakuten candidate into the user's closet (MK-6).

    Only candidates already proposed into the caller's own session can be
    imported; arbitrary external URLs are rejected by construction.
    """

    def __init__(
        self,
        styling_repo: StylingRepositoryPort,
        closet_repo: ClosetRepositoryPort,
        image_storage: ImageStoragePort,
        embedding_search: EmbeddingSearchPort,
        image_fetcher: Callable[[str], Awaitable[bytes]] = _fetch_external_image,
    ):
        self.styling_repo = styling_repo
        self.closet_repo = closet_repo
        self.image_storage = image_storage
        self.embedding_search = embedding_search
        self.image_fetcher = image_fetcher

    async def execute(self, user_id: str, session_id: str, candidate_id: str) -> dict:
        session = await self.styling_repo.get_by_id(
            user_id, StyleSessionId(UUID(session_id))
        )
        if session is None:
            raise StyleSessionNotFound(f"Style session not found: {session_id}")

        candidate = next(
            (
                item
                for item in session.proposed_candidates
                if str(item.get("item_id") or item.get("itemId")) == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError(f"Candidate not proposed in this session: {candidate_id}")
        if candidate.get("source") != "RAKUTEN":
            raise ValueError("Only RAKUTEN suggestions can be imported")
        image_url = candidate.get("image_url") or candidate.get("imageUrl")
        if not image_url:
            raise ValueError("Candidate has no image to import")

        count = await self.closet_repo.count_by_user(user_id)
        if count >= get_settings().max_closet_images_per_user:
            raise MaxClosetItemsExceeded("Maximum closet item count reached")

        data = await self.image_fetcher(image_url)
        new_id = uuid4()
        image_path = f"{user_id}/closet/{new_id}.jpg"
        await self.image_storage.put_image_bytes(image_path, data)

        tags = [
            ClothingTag(name="tag", value=str(value))
            for value in candidate.get("tags") or []
            if str(value)
        ]
        item = ClothingItem(
            id=ClothingItemId(new_id),
            user_id=user_id,
            image_url=image_path,
            tags=tags,
            status=ClothingItemStatus.READY,
            category=candidate.get("category"),
            colors=list(candidate.get("colors") or []),
            season=candidate.get("season"),
            gender=candidate.get("gender"),
            ownership_status=ClosetOwnershipStatus.INTERESTING,
            origin="RAKUTEN",
            external_item_id=candidate_id,
            external_url=candidate.get("external_url") or candidate.get("externalUrl"),
            affiliate_url=candidate.get("affiliate_url") or candidate.get("affiliateUrl"),
            price=candidate.get("price"),
            brand_or_shop=candidate.get("shop_name") or candidate.get("shopName"),
        )
        await self.closet_repo.create(item)

        try:
            await self.embedding_search.index_item(
                item_id=str(new_id),
                user_id=user_id,
                is_shared=False,
                tags=[tag.value for tag in item.tags],
                category=item.category,
                colors=item.colors,
                season=item.season,
                embedding=None,
                gender=item.gender,
                ownership_status=item.ownership_status.value,
                origin=item.origin,
                external_item_id=item.external_item_id,
                external_url=item.external_url,
            )
        except Exception:
            # Fail-soft like the metadata path; the item is still usable and a
            # later metadata update can reindex it.
            logger.exception("Failed to index imported closet item %s", new_id)

        return {
            "item_id": str(new_id),
            "status": item.status.value,
            "ownershipStatus": item.ownership_status.value,
        }
