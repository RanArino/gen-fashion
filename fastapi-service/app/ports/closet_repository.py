from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.closet import ClothingItem, ClothingItemId


class ClosetRepositoryPort(ABC):
    """Port for closet repository operations (CRUD for closet metadata)."""

    @abstractmethod
    async def create(self, item: ClothingItem) -> None:
        """Create a new clothing item."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    @abstractmethod
    async def get_by_id(self, user_id: str, item_id: ClothingItemId) -> Optional[ClothingItem]:
        """Get a clothing item by ID."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    @abstractmethod
    async def get_all_by_user(self, user_id: str) -> List[ClothingItem]:
        """Get all clothing items for a user."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    @abstractmethod
    async def update(self, item: ClothingItem) -> None:
        """Update a clothing item."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    @abstractmethod
    async def delete(self, user_id: str, item_id: ClothingItemId) -> None:
        """Delete a clothing item."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")

    @abstractmethod
    async def count_by_user(self, user_id: str) -> int:
        """Count total items in a user's closet."""
        raise NotImplementedError("Implement in M2-8: Firestore adapter")
