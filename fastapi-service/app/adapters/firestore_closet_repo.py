from datetime import datetime
from typing import List, Optional
from uuid import UUID
from google.cloud import firestore
from app.ports import ClosetRepositoryPort
from app.config import get_settings
from app.domain.closet import (
    ClosetOwnershipStatus,
    ClothingItem,
    ClothingItemId,
    ClothingItemStatus,
    ClothingTag,
    IntentTag,
)
from app.domain.closet.value_objects import ImageEmbedding


class FirestoreClosetRepository(ClosetRepositoryPort):
    """Firestore adapter for closet repository (M2-8)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = firestore.AsyncClient(
            project=settings.firestore_project_id,
            database=settings.firestore_database_id,
        )

    def _collection(self, user_id: str):
        return self._client.collection("users").document(user_id).collection("closet")

    def _document(self, user_id: str, item_id: ClothingItemId):
        return self._collection(user_id).document(str(item_id))

    @staticmethod
    def _tag_values(tags: List[ClothingTag]) -> List[str]:
        return [tag.value for tag in tags]

    @staticmethod
    def _tags_from_values(values: List[str]) -> List[ClothingTag]:
        return [ClothingTag(name="tag", value=value) for value in values]

    @staticmethod
    def _to_document(item: ClothingItem) -> dict:
        data = {
            "itemId": str(item.id),
            "userId": item.user_id,
            "imageUrl": item.image_url,
            "status": item.status.value,
            "category": item.category,
            "colors": item.colors,
            "season": item.season,
            "gender": item.gender,
            "tags": FirestoreClosetRepository._tag_values(item.tags),
            "embeddingId": str(item.id) if item.status == ClothingItemStatus.READY else None,
            "ownershipStatus": item.ownership_status.value,
            "origin": item.origin,
            "externalItemId": item.external_item_id,
            "externalUrl": item.external_url,
            "affiliateUrl": item.affiliate_url,
            "price": item.price,
            "brandOrShop": item.brand_or_shop,
            "intentTags": [tag.value for tag in item.intent_tags],
            "intentVocabularyVersion": item.intent_vocabulary_version,
            "createdAt": item.created_at,
            "updatedAt": item.updated_at,
        }
        return {key: value for key, value in data.items() if value is not None}

    @staticmethod
    def _parse_datetime(value):
        if isinstance(value, datetime) or value is None:
            return value
        if hasattr(value, "datetime"):
            return value.datetime
        return value

    @staticmethod
    def _from_snapshot(snapshot) -> ClothingItem | None:
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        vector = data.get("embedding")
        embedding = None
        if vector:
            embedding = ImageEmbedding(
                vector=vector,
                model=data.get("embeddingModel", "unknown"),
                created_at=str(data.get("updatedAt") or ""),
            )
        return ClothingItem(
            id=ClothingItemId(UUID(snapshot.id)),
            user_id=data.get("userId") or snapshot.reference.parent.parent.id,
            image_url=data["imageUrl"],
            tags=FirestoreClosetRepository._tags_from_values(data.get("tags", [])),
            embedding=embedding,
            status=ClothingItemStatus(data.get("status", ClothingItemStatus.PROCESSING)),
            category=data.get("category"),
            colors=data.get("colors", []),
            season=data.get("season"),
            gender=data.get("gender"),
            created_at=FirestoreClosetRepository._parse_datetime(data.get("createdAt")),
            updated_at=FirestoreClosetRepository._parse_datetime(data.get("updatedAt")),
            # Pre-MK documents have no ownershipStatus; they are user uploads.
            ownership_status=ClosetOwnershipStatus(
                data.get("ownershipStatus", ClosetOwnershipStatus.OWNED)
            ),
            origin=data.get("origin"),
            external_item_id=data.get("externalItemId"),
            external_url=data.get("externalUrl"),
            affiliate_url=data.get("affiliateUrl"),
            price=data.get("price"),
            brand_or_shop=data.get("brandOrShop"),
            intent_tags=[IntentTag(value) for value in data.get("intentTags", [])],
            intent_vocabulary_version=data.get("intentVocabularyVersion"),
        )

    async def create(self, item: ClothingItem) -> None:
        await self._document(item.user_id, item.id).set(self._to_document(item))

    async def get_by_id(self, user_id: str, item_id: ClothingItemId) -> Optional[ClothingItem]:
        snapshot = await self._document(user_id, item_id).get()
        return self._from_snapshot(snapshot)

    async def get_all_by_user(self, user_id: str) -> List[ClothingItem]:
        items = []
        async for snapshot in self._collection(user_id).stream():
            item = self._from_snapshot(snapshot)
            if item is not None:
                items.append(item)
        return items

    async def update(self, item: ClothingItem) -> None:
        await self._document(item.user_id, item.id).set(self._to_document(item), merge=True)

    async def delete(self, user_id: str, item_id: ClothingItemId) -> None:
        await self._document(user_id, item_id).delete()

    async def count_by_user(self, user_id: str) -> int:
        aggregation = self._collection(user_id).count()
        results = await aggregation.get()
        if not results:
            return 0
        return results[0][0].value
