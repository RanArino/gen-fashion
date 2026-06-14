from uuid import UUID
from app.domain.styling import StyleSessionId
from app.ports import StylingRepositoryPort


class AnalyzeClothingImageUseCase:
    """Use case for analyzing uploaded image (M5-4)."""

    def __init__(self, styling_repo: StylingRepositoryPort):
        self.styling_repo = styling_repo

    async def execute(self, user_id: str, session_id: str, image_url: str) -> None:
        session = await self.styling_repo.get_by_id(user_id, StyleSessionId(UUID(session_id)))
        if session is not None:
            session.upload_image(image_url)
            session.analyze()
            await self.styling_repo.update(session)
