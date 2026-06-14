from dataclasses import dataclass
from uuid import uuid4
from app.ports import StylingRepositoryPort
from app.domain.styling import ClothingSource, StyleSession, StyleSessionId, StyleSessionState


@dataclass(frozen=True)
class CreateSessionResult:
    session_id: str
    status: str
    source: str


class CreateSessionUseCase:
    """Use case for creating a style session (M5-1)."""

    def __init__(self, styling_repo: StylingRepositoryPort):
        self.styling_repo = styling_repo

    async def execute(self, user_id: str) -> CreateSessionResult:
        session = StyleSession(
            id=StyleSessionId(uuid4()),
            user_id=user_id,
            state=StyleSessionState.SOURCE_SELECTING,
            clothing_source=ClothingSource.UNSET,
        )
        await self.styling_repo.create(session)
        return CreateSessionResult(
            session_id=str(session.id),
            status=session.state.value,
            source=session.clothing_source.value,
        )
