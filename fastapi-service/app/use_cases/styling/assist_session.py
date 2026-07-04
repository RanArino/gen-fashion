from dataclasses import dataclass
from uuid import UUID

from app.config import Settings, get_settings
from app.domain.closet import ClothingItem, ClothingItemStatus
from app.domain.styling import (
    StyleSessionId,
    StyleSessionNotFound,
    StyleSessionState,
    UserPreference,
)
from app.ports import (
    AgentRunPort,
    AgentRunRequest,
    ClosetRepositoryPort,
    ImageStoragePort,
    StylingRepositoryPort,
)
from app.use_cases.styling.daily_generation_limit import enforce_daily_generation_limit
from app.use_cases.styling.select_source import AgentRunStartFailed

MAX_ASSISTED_ANCHOR_ITEMS = 3


@dataclass(frozen=True)
class AssistSessionResult:
    session_id: str
    status: str
    source: str


class AssistSessionUseCase:
    """Start an Assisted Coordinate propose run from 1..3 own anchors (MK)."""

    def __init__(
        self,
        styling_repo: StylingRepositoryPort,
        closet_repo: ClosetRepositoryPort,
        image_storage: ImageStoragePort,
        agent_run: AgentRunPort,
        settings: Settings | None = None,
    ):
        self.styling_repo = styling_repo
        self.closet_repo = closet_repo
        self.image_storage = image_storage
        self.agent_run = agent_run
        self._settings = settings or get_settings()

    async def execute(
        self,
        user_id: str,
        session_id: str,
        anchor_item_ids: list[str],
        preference: UserPreference,
    ) -> AssistSessionResult:
        if not 1 <= len(anchor_item_ids) <= MAX_ASSISTED_ANCHOR_ITEMS:
            raise ValueError(
                f"anchorItemIds must contain 1 to {MAX_ASSISTED_ANCHOR_ITEMS} items"
            )
        if len(set(anchor_item_ids)) != len(anchor_item_ids):
            raise ValueError("anchorItemIds must not contain duplicates")

        session = await self.styling_repo.get_by_id(user_id, StyleSessionId(UUID(session_id)))
        if session is None:
            raise StyleSessionNotFound(f"Style session not found: {session_id}")
        if session.state != StyleSessionState.SOURCE_SELECTING:
            raise ValueError(f"Cannot select source from {session.state.value}")

        items = {str(item.id): item for item in await self.closet_repo.get_all_by_user(user_id)}
        anchors = []
        for item_id in anchor_item_ids:
            item = items.get(item_id)
            if item is None:
                raise ValueError(f"Anchor item not found in your closet: {item_id}")
            if item.status != ClothingItemStatus.READY:
                raise ValueError(f"Anchor item is not READY: {item_id}")
            anchors.append(await self._anchor_candidate(item))

        await enforce_daily_generation_limit(self.styling_repo, self._settings, user_id)

        session.select_assisted(anchors, preference)
        await self.styling_repo.update(session)
        try:
            await self.agent_run.start_session_run(
                AgentRunRequest(
                    session_id=session_id,
                    user_id=user_id,
                    source=session.clothing_source.value,
                    user_preference={
                        "occasion": preference.occasion,
                        "season": preference.season,
                        "style": preference.style,
                        "colorPreference": preference.color_preference,
                        "gender": preference.gender,
                        "language": preference.language,
                    },
                    phase="propose",
                    mode="assisted",
                    anchor_items=anchors,
                )
            )
        except Exception as exc:
            session.mark_error()
            await self.styling_repo.update(session)
            raise AgentRunStartFailed("Failed to start assisted styling run") from exc
        return AssistSessionResult(
            session_id=session_id,
            status=session.state.value,
            source=session.clothing_source.value,
        )

    async def _anchor_candidate(self, item: ClothingItem) -> dict:
        try:
            image_url = await self.image_storage.get_download_url(item.image_url)
        except Exception:
            image_url = ""
        return {
            "item_id": str(item.id),
            "source": "CLOSET",
            "image_url": image_url,
            "category": item.category,
            "tags": [tag.value for tag in item.tags],
            "colors": item.colors,
            "season": item.season,
            "gender": item.gender or "common",
            "anchor": True,
            "recommended": True,
        }
