from abc import ABC, abstractmethod
from typing import Optional
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
    async def delete(self, user_id: str, session_id: StyleSessionId) -> None:
        """Delete a styling session."""
        raise NotImplementedError("Implement in M5-2: Firestore adapter")
