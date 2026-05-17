from uuid import UUID
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
from app.domain.shared.base_models import AggregateRoot
from app.domain.closet.value_objects import ClothingItemId, ClothingTag, ImageEmbedding


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
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        """Validate invariants."""
        if not self.user_id:
            raise ValueError("user_id must not be empty")
        if not self.image_url:
            raise ValueError("image_url must not be empty")
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

    def _mark_updated(self) -> None:
        """Mark the item as updated."""
        object.__setattr__(self, 'updated_at', datetime.utcnow())
