from dataclasses import dataclass
from uuid import UUID

from app.domain.closet import ClothingItemStatus
from app.domain.styling import (
    ClothingSource,
    StyleSessionId,
    StyleSessionNotFound,
    StyleSessionState,
    UserPreference,
)
from app.ports import AgentRunPort, AgentRunRequest, ClosetRepositoryPort, StylingRepositoryPort


@dataclass(frozen=True)
class SelectSourceResult:
    session_id: str
    status: str
    source: str


class AgentRunStartFailed(RuntimeError):
    """Raised when the ADK session run cannot be accepted."""


class SelectClothingSourceUseCase:
    """Use case for selecting clothing source (M5-3)."""

    def __init__(
        self,
        styling_repo: StylingRepositoryPort,
        closet_repo: ClosetRepositoryPort,
        agent_run: AgentRunPort,
    ):
        self.styling_repo = styling_repo
        self.closet_repo = closet_repo
        self.agent_run = agent_run

    async def execute(
        self,
        user_id: str,
        session_id: str,
        source: ClothingSource,
        preference: UserPreference,
        shared_closet_id: str | None = None,
    ) -> SelectSourceResult:
        if source == ClothingSource.UNSET:
            raise ValueError("source must be CLOSET or SHARED_CLOSET")
        if source == ClothingSource.RAKUTEN:
            raise ValueError("RAKUTEN is not available in Phase 1a")

        session = await self.styling_repo.get_by_id(user_id, StyleSessionId(UUID(session_id)))
        if session is None:
            raise StyleSessionNotFound(f"Style session not found: {session_id}")
        if session.state != StyleSessionState.SOURCE_SELECTING:
            raise ValueError(f"Cannot select source from {session.state.value}")

        if source == ClothingSource.CLOSET:
            items = await self.closet_repo.get_all_by_user(user_id)
            ready_items = [item for item in items if item.status == ClothingItemStatus.READY]
            if not ready_items:
                raise ValueError("CLOSET requires at least one READY closet item")

        session.select_source(source, preference, shared_closet_id)
        await self.styling_repo.update(session)
        try:
            await self.agent_run.start_session_run(
                AgentRunRequest(
                    session_id=session_id,
                    user_id=user_id,
                    source=source.value,
                    shared_closet_id=shared_closet_id,
                    user_preference={
                        "occasion": preference.occasion,
                        "season": preference.season,
                        "style": preference.style,
                        "colorPreference": preference.color_preference,
                    },
                )
            )
        except Exception as exc:
            session.mark_error()
            await self.styling_repo.update(session)
            raise AgentRunStartFailed("Failed to start styling run") from exc
        return SelectSourceResult(
            session_id=session_id,
            status=session.state.value,
            source=session.clothing_source.value,
        )
