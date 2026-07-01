from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.config import Settings, get_settings
from app.domain.styling import StyleSessionId, StyleSessionNotFound, StyleSessionState
from app.domain.styling.exceptions import DailyGenerationLimitExceeded
from app.ports import AgentRunPort, AgentRunRequest, StylingRepositoryPort
from app.use_cases.styling.select_source import AgentRunStartFailed


@dataclass(frozen=True)
class SelectCandidatesResult:
    session_id: str
    status: str
    source: str


class SelectCandidatesUseCase:
    """Persist explicit candidate consent and trigger generation."""

    def __init__(
        self,
        styling_repo: StylingRepositoryPort,
        agent_run: AgentRunPort,
        settings: Settings | None = None,
    ):
        self.styling_repo = styling_repo
        self.agent_run = agent_run
        self._settings = settings or get_settings()

    async def execute(
        self, user_id: str, session_id: str, selected_item_ids: list[str]
    ) -> SelectCandidatesResult:
        session = await self.styling_repo.get_by_id(
            user_id, StyleSessionId(UUID(session_id))
        )
        if session is None:
            raise StyleSessionNotFound(f"Style session not found: {session_id}")
        if session.state != StyleSessionState.PROPOSING:
            raise ValueError(f"Cannot select candidates from {session.state.value}")
        if not selected_item_ids:
            raise ValueError("At least one candidate must be selected")

        by_id = {
            str(item.get("item_id") or item.get("itemId")): item
            for item in session.proposed_candidates
        }
        unknown = [item_id for item_id in selected_item_ids if item_id not in by_id]
        if unknown:
            raise ValueError(f"Unknown candidate ids: {', '.join(unknown)}")
        selected = [by_id[item_id] for item_id in selected_item_ids]
        if self._settings.max_daily_generations_per_user > 0:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            count = await self.styling_repo.count_completed_today(user_id, today_start)
            if count >= self._settings.max_daily_generations_per_user:
                raise DailyGenerationLimitExceeded(
                    f"Daily generation limit of "
                    f"{self._settings.max_daily_generations_per_user} reached. "
                    f"Limit resets at midnight UTC."
                )
        session.select_candidates(selected)
        await self.styling_repo.update(session)
        preference = session.user_preference
        try:
            await self.agent_run.start_session_run(
                AgentRunRequest(
                    session_id=session_id,
                    user_id=user_id,
                    source=session.clothing_source.value,
                    shared_closet_id=session.shared_closet_id,
                    user_preference={
                        "occasion": preference.occasion if preference else None,
                        "season": preference.season if preference else None,
                        "style": preference.style if preference else None,
                        "colorPreference": preference.color_preference if preference else None,
                        "gender": preference.gender if preference else None,
                    },
                    phase="generate",
                    selected_items=selected,
                )
            )
        except Exception as exc:
            session.mark_error()
            await self.styling_repo.update(session)
            raise AgentRunStartFailed("Failed to start coordinate generation") from exc
        return SelectCandidatesResult(
            session_id=session_id,
            status=session.state.value,
            source=session.clothing_source.value,
        )
