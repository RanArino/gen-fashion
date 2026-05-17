from abc import ABC, abstractmethod
from typing import List
from app.domain.styling import CandidateItem, ClothingSource


class ClothingSearchPort(ABC):
    """Port for unified cross-modal search over closet items, shared closet, and external sources."""

    @abstractmethod
    async def search_by_source(
        self, user_id: str, source: ClothingSource, query: str, limit: int = 10
    ) -> List[CandidateItem]:
        """
        Search for clothing candidates from a specific source.
        Routes to appropriate adapter (closet, shared, Rakuten).
        """
        raise NotImplementedError("Implement in M5-5: Unified search adapter")

    @abstractmethod
    async def search_all_sources(
        self, user_id: str, sources: List[ClothingSource], query: str, limit: int = 10
    ) -> List[CandidateItem]:
        """Search across multiple sources and return unified results."""
        raise NotImplementedError("Implement in M5-5: Unified search adapter")
