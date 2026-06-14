from uuid import UUID
from app.domain.styling import StyleSessionId
from app.ports import StylingRepositoryPort, ImageGenerationPort


class GenerateCoordinateUseCase:
    """Use case for generating final coordinate image (M5-6)."""

    def __init__(self, styling_repo: StylingRepositoryPort, image_gen: ImageGenerationPort):
        self.styling_repo = styling_repo
        self.image_gen = image_gen

    async def execute(self, user_id: str, session_id: str, item_ids: list) -> str:
        session = await self.styling_repo.get_by_id(user_id, StyleSessionId(UUID(session_id)))
        if session is None:
            return ""
        session.set_selected_items([{"itemId": item_id} for item_id in item_ids])
        await self.styling_repo.update(session)
        return ""
