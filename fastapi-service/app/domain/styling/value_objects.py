from uuid import UUID
from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional, List
from app.domain.shared.base_models import ValueObject


class ClothingSource(str, Enum):
    """Source of clothing candidates."""
    UNSET = "UNSET"
    CLOSET = "CLOSET"
    SHARED_CLOSET = "SHARED_CLOSET"
    RAKUTEN = "RAKUTEN"


@dataclass(frozen=True)
class StyleSessionId(ValueObject):
    """Unique identifier for a styling session."""
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class UserPreference(ValueObject):
    """User's styling preferences for a session."""
    occasion: Optional[str] = None
    season: Optional[str] = None
    style: Optional[str] = None
    color_preference: Optional[str] = None


@dataclass(frozen=True)
class CandidateItem(ValueObject):
    """A candidate clothing item for coordination."""
    item_id: str
    source: ClothingSource
    image_url: str
    tags: List[str]
    name: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    external_url: Optional[str] = None
    attribution: Optional[str] = None


@dataclass(frozen=True)
class CoordinateProposal(ValueObject):
    """A proposed coordinate (outfit) from the styling agent."""
    items: List[CandidateItem]
    reasoning: str


@dataclass(frozen=True)
class StyleResult(ValueObject):
    """Final styling result with generated image."""
    coordinate_image_url: str
    proposal: Optional[CoordinateProposal] = None
    model_used: Optional[str] = None
    raw_payload: Optional[dict[str, Any]] = None
