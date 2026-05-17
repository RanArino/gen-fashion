from app.ports import StylingRepositoryPort


class AnalyzeClothingImageUseCase:
    """Use case for analyzing uploaded image (M5-4)."""

    def __init__(self, styling_repo: StylingRepositoryPort):
        self.styling_repo = styling_repo

    async def execute(self, user_id: str, session_id: str, image_url: str) -> None:
        raise NotImplementedError("Implement in M5-4: Analyze image")
