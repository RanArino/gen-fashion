from uuid import UUID
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from app.domain.shared.base_models import AggregateRoot
from app.domain.closet.value_objects import (
    ClosetOwnershipStatus,
    ClothingItemId,
    ClothingItemStatus,
    ClothingTag,
    ImageEmbedding,
)


@dataclass
class ClothingItem(AggregateRoot):
    """
    Aggregate root for a clothing item in the closet.
    Represents a single piece of clothing with metadata and embeddings.
    """

    id: ClothingItemId
    user_id: str
    image_url: str
    tags: List[ClothingTag]
    embedding: Optional[ImageEmbedding] = None
    status: ClothingItemStatus = ClothingItemStatus.PROCESSING
    category: Optional[str] = None
    colors: List[str] = None
    season: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    ownership_status: ClosetOwnershipStatus = ClosetOwnershipStatus.OWNED
    origin: Optional[str] = None  # USER_UPLOAD | RAKUTEN
    external_item_id: Optional[str] = None
    external_url: Optional[str] = None
    affiliate_url: Optional[str] = None
    price: Optional[float] = None
    brand_or_shop: Optional[str] = None

    def __post_init__(self):
        """Validate invariants."""
        if not self.user_id:
            raise ValueError("user_id must not be empty")
        if not self.image_url:
            raise ValueError("image_url must not be empty")
        if self.colors is None:
            object.__setattr__(self, 'colors', [])
        if self.created_at is None:
            object.__setattr__(self, 'created_at', datetime.utcnow())
        if self.updated_at is None:
            object.__setattr__(self, 'updated_at', datetime.utcnow())

    def add_tag(self, tag: ClothingTag) -> None:
        """Add a tag to the clothing item."""
        if tag not in self.tags:
            self.tags.append(tag)
            self._mark_updated()

    def set_embedding(self, embedding: ImageEmbedding) -> None:
        """Set the embedding for this item."""
        object.__setattr__(self, 'embedding', embedding)
        self._mark_updated()

    def mark_ready(
        self,
        category: Optional[str],
        colors: List[str],
        season: Optional[str],
        gender: Optional[str],
        tags: List[ClothingTag],
        embedding: Optional[ImageEmbedding] = None,
    ) -> None:
        """Mark analysis as complete and store extracted metadata."""
        object.__setattr__(self, 'status', ClothingItemStatus.READY)
        object.__setattr__(self, 'category', category)
        object.__setattr__(self, 'colors', colors)
        object.__setattr__(self, 'season', season)
        object.__setattr__(self, 'gender', gender)
        object.__setattr__(self, 'tags', tags)
        object.__setattr__(self, 'embedding', embedding)
        self._mark_updated()

    def set_metadata(
        self,
        *,
        gender: Optional[str] = None,
        category: Optional[str] = None,
        colors: Optional[List[str]] = None,
        season: Optional[str] = None,
        tags: Optional[List[ClothingTag]] = None,
    ) -> None:
        """Update user-correctable searchable metadata."""
        if gender is not None:
            if gender not in {"male", "female", "common"}:
                raise ValueError("gender must be male, female, or common")
            object.__setattr__(self, 'gender', gender)
        if category is not None:
            object.__setattr__(self, 'category', category)
        if colors is not None:
            object.__setattr__(self, 'colors', colors)
        if season is not None:
            object.__setattr__(self, 'season', season)
        if tags is not None:
            object.__setattr__(self, 'tags', tags)
        self._mark_updated()

    def set_ownership_status(self, ownership_status: ClosetOwnershipStatus) -> None:
        """Switch between OWNED and INTERESTING."""
        object.__setattr__(self, 'ownership_status', ownership_status)
        self._mark_updated()

    def mark_error(self) -> None:
        """Mark analysis as failed."""
        object.__setattr__(self, 'status', ClothingItemStatus.ERROR)
        self._mark_updated()

    def _mark_updated(self) -> None:
        """Mark the item as updated."""
        object.__setattr__(self, 'updated_at', datetime.utcnow())
