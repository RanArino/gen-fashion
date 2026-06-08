from typing import Optional
from app.ports import StylingRepositoryPort
from app.domain.styling import StyleSession, StyleSessionId


class FirestoreStylingRepository(StylingRepositoryPort):
    """Firestore adapter for styling session persistence (M5-2)."""

    async def create(self, session: StyleSession) -> None:
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    async def get_by_id(self, user_id: str, session_id: StyleSessionId) -> Optional[StyleSession]:
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    async def update(self, session: StyleSession) -> None:
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    async def delete(self, user_id: str, session_id: StyleSessionId) -> None:
        raise NotImplementedError("Implement in M5-2: Firestore adapter")
