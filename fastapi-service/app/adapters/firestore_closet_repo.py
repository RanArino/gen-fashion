from typing import List, Optional
from app.ports import ClosetRepositoryPort
from app.domain.closet import ClothingItem, ClothingItemId


class FirestoreClosetRepository(ClosetRepositoryPort):
    """Firestore adapter for closet repository (M2-8)."""

    async def create(self, item: ClothingItem) -> None:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    async def get_by_id(self, user_id: str, item_id: ClothingItemId) -> Optional[ClothingItem]:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    async def get_all_by_user(self, user_id: str) -> List[ClothingItem]:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    async def update(self, item: ClothingItem) -> None:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    async def delete(self, user_id: str, item_id: ClothingItemId) -> None:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    async def count_by_user(self, user_id: str) -> int:
        raise NotImplementedError("Implement in M2-8: Firestore adapter")
