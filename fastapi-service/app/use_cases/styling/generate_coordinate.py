from app.ports import StylingRepositoryPort, ImageGenerationPort


class GenerateCoordinateUseCase:
    """Use case for generating final coordinate image (M5-6)."""

    def __init__(self, styling_repo: StylingRepositoryPort, image_gen: ImageGenerationPort):
        self.styling_repo = styling_repo
        self.image_gen = image_gen

    async def execute(self, user_id: str, session_id: str, item_ids: list) -> str:
        raise NotImplementedError("Implement in M5-6: Generate coordinate")
