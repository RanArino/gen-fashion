from abc import ABC, abstractmethod
from typing import Any, Optional
from app.domain.styling import StyleSession, StyleSessionId


class StylingRepositoryPort(ABC):
    """Port for styling session persistence and state machine."""

    @abstractmethod
    async def create(self, session: StyleSession) -> None:
        """Create a new styling session."""
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    @abstractmethod
    async def get_by_id(self, user_id: str, session_id: StyleSessionId) -> Optional[StyleSession]:
        """Get a styling session by ID."""
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    @abstractmethod
    async def update(self, session: StyleSession) -> None:
        """Update a styling session (state transitions, results)."""
        raise NotImplementedError("Implement in M5-2: Firestore adapter")

    @abstractmethod
    async def list_completed(self, user_id: str, limit: int = 20) -> list[StyleSession]:
        """List the user's completed styling sessions, newest first."""
        raise NotImplementedError

    @abstractmethod
    async def list_events(
        self, user_id: str, session_id: StyleSessionId, after_seq: int = 0
    ) -> list[dict[str, Any]]:
        """List normalized agent events for a session in seq order."""
        raise NotImplementedError("Implement in M5-9: Firestore event stream")

    @abstractmethod
    async def delete(self, user_id: str, session_id: StyleSessionId) -> None:
        """Delete a styling session."""
        raise NotImplementedError("Implement in M5-2: Firestore adapter")
