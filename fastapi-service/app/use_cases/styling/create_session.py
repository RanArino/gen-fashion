from app.ports import StylingRepositoryPort


class CreateSessionUseCase:
    """Use case for creating a style session (M5-1)."""

    def __init__(self, styling_repo: StylingRepositoryPort):
        self.styling_repo = styling_repo

    async def execute(self, user_id: str) -> str:
        raise NotImplementedError("Implement in M5-1: Create session")
