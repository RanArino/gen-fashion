from app.ports import StylingRepositoryPort, ClosetRepositoryPort
from app.domain.styling import ClothingSource


class SelectClothingSourceUseCase:
    """Use case for selecting clothing source (M5-3)."""

    def __init__(self, styling_repo: StylingRepositoryPort, closet_repo: ClosetRepositoryPort):
        self.styling_repo = styling_repo
        self.closet_repo = closet_repo

    async def execute(self, user_id: str, session_id: str, source: ClothingSource) -> None:
        raise NotImplementedError("Implement in M5-3: Select source")
