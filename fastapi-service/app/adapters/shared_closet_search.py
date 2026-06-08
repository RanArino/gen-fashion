from typing import List
from app.ports import ClothingSearchPort
from app.domain.styling import CandidateItem, ClothingSource


class SharedClosetSearchAdapter(ClothingSearchPort):
    """Adapter for searching shared closet (M3-3)."""

    async def search_by_source(
        self, user_id: str, source: ClothingSource, query: str, limit: int = 10
    ) -> List[CandidateItem]:
        raise NotImplementedError("Implement in M3-3: Shared closet search")

    async def search_all_sources(
        self, user_id: str, sources: List[ClothingSource], query: str, limit: int = 10
    ) -> List[CandidateItem]:
        raise NotImplementedError("Implement in M3-3: Shared closet search")
