from uuid import UUID
from typing import List
from dataclasses import dataclass
from app.domain.shared.base_models import ValueObject


@dataclass(frozen=True)
class ClothingItemId(ValueObject):
    """Unique identifier for a clothing item."""
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class ClothingTag(ValueObject):
    """A tag describing clothing attributes (color, style, category)."""
    name: str
    value: str

    def __post_init__(self):
        if not self.name or not self.value:
            raise ValueError("ClothingTag name and value must not be empty")


@dataclass(frozen=True)
class ImageEmbedding(ValueObject):
    """Vector embedding of a clothing item image."""
    vector: List[float]
    model: str
    created_at: str

    def __post_init__(self):
        if len(self.vector) == 0:
            raise ValueError("ImageEmbedding vector must not be empty")
        if not self.model:
            raise ValueError("ImageEmbedding model must not be empty")
