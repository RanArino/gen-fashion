from app.ports import ClothingSearchPort
from app.domain.styling import ClothingSource


class SearchCandidateItemsUseCase:
    """Use case for searching candidate items (M5-5)."""

    def __init__(self, clothing_search: ClothingSearchPort):
        self.clothing_search = clothing_search

    async def execute(
        self,
        user_id: str,
        session_id: str,
        query: str,
        source: ClothingSource = ClothingSource.SHARED_CLOSET,
    ) -> list:
        return await self.clothing_search.search_by_source(user_id, source, query)
