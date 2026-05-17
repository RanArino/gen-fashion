from app.ports import ClothingSearchPort


class SearchCandidateItemsUseCase:
    """Use case for searching candidate items (M5-5)."""

    def __init__(self, clothing_search: ClothingSearchPort):
        self.clothing_search = clothing_search

    async def execute(self, user_id: str, session_id: str, query: str) -> list:
        raise NotImplementedError("Implement in M5-5: Search candidates")
