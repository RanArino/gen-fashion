from uuid import UUID, uuid4

import pytest

from app.config import Settings
from app.domain.closet import ClothingItem, ClothingItemId, ClothingItemStatus
from app.domain.styling import (
    ClothingSource,
    StyleSession,
    StyleSessionId,
    StyleSessionNotFound,
    StyleSessionState,
    UserPreference,
)
from app.domain.styling.exceptions import DailyGenerationLimitExceeded
from app.ports import AgentRunRequest
from app.use_cases.styling import (
    CreateSessionUseCase,
    SelectCandidatesUseCase,
    SelectClothingSourceUseCase,
)


class FakeStylingRepo:
    def __init__(self):
        self.sessions = {}
        self.completed_today_count = 0
        self.count_completed_today_calls = []

    async def create(self, session):
        self.sessions[(session.user_id, str(session.id))] = session

    async def get_by_id(self, user_id, session_id):
        return self.sessions.get((user_id, str(session_id)))

    async def update(self, session):
        self.sessions[(session.user_id, str(session.id))] = session

    async def list_completed(self, user_id, limit=20):
        return []

    async def count_completed_today(self, user_id, since):
        self.count_completed_today_calls.append((user_id, since))
        return self.completed_today_count

    async def list_events(self, user_id, session_id):
        return []

    async def delete(self, user_id, session_id):
        self.sessions.pop((user_id, str(session_id)), None)


class FakeClosetRepo:
    def __init__(self, items=None):
        self.items = items or []

    async def create(self, item):
        self.items.append(item)

    async def get_by_id(self, user_id, item_id):
        return None

    async def get_all_by_user(self, user_id):
        return [item for item in self.items if item.user_id == user_id]

    async def update(self, item):
        pass

    async def delete(self, user_id, item_id):
        pass

    async def count_by_user(self, user_id):
        return len(await self.get_all_by_user(user_id))


class FakeAgentRun:
    def __init__(self):
        self.requests: list[AgentRunRequest] = []

    async def start_session_run(self, request):
        self.requests.append(request)


class FailingAgentRun:
    async def start_session_run(self, request):
        raise RuntimeError("ADK unavailable")


def ready_item(user_id="user-123"):
    item_id = uuid4()
    return ClothingItem(
        id=ClothingItemId(item_id),
        user_id=user_id,
        image_url=f"{user_id}/closet/{item_id}.jpg",
        tags=[],
        status=ClothingItemStatus.READY,
    )


@pytest.mark.asyncio
async def test_create_session_creates_source_selecting_unset_session():
    repo = FakeStylingRepo()

    result = await CreateSessionUseCase(repo).execute("user-123")

    session = await repo.get_by_id("user-123", StyleSessionId(UUID(result.session_id)))
    assert result.status == "SOURCE_SELECTING"
    assert result.source == "UNSET"
    assert session.state == StyleSessionState.SOURCE_SELECTING
    assert session.clothing_source == ClothingSource.UNSET


@pytest.mark.asyncio
async def test_select_source_accepts_shared_closet_and_triggers_agent():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )
    agent_run = FakeAgentRun()

    result = await SelectClothingSourceUseCase(repo, FakeClosetRepo(), agent_run).execute(
        "user-123",
        str(session_id),
        ClothingSource.SHARED_CLOSET,
        UserPreference(occasion="work", style="clean"),
        "adult-01",
    )

    assert result.status == "SEARCHING"
    assert result.source == "SHARED_CLOSET"
    assert agent_run.requests[0].session_id == str(session_id)
    assert agent_run.requests[0].shared_closet_id == "adult-01"
    assert agent_run.requests[0].user_preference["style"] == "clean"


@pytest.mark.asyncio
async def test_select_source_marks_error_when_agent_trigger_fails():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )

    with pytest.raises(RuntimeError, match="Failed to start styling run"):
        await SelectClothingSourceUseCase(repo, FakeClosetRepo(), FailingAgentRun()).execute(
            "user-123",
            str(session_id),
            ClothingSource.SHARED_CLOSET,
            UserPreference(),
            "adult-01",
        )

    session = await repo.get_by_id("user-123", StyleSessionId(session_id))
    assert session.state == StyleSessionState.ERROR


@pytest.mark.asyncio
async def test_select_source_rejects_empty_closet():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )

    with pytest.raises(ValueError, match="READY"):
        await SelectClothingSourceUseCase(repo, FakeClosetRepo(), FakeAgentRun()).execute(
            "user-123",
            str(session_id),
            ClothingSource.CLOSET,
            UserPreference(),
        )


@pytest.mark.asyncio
async def test_select_source_accepts_ready_closet_item():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )
    agent_run = FakeAgentRun()

    await SelectClothingSourceUseCase(
        repo,
        FakeClosetRepo([ready_item()]),
        agent_run,
    ).execute("user-123", str(session_id), ClothingSource.CLOSET, UserPreference())

    assert agent_run.requests[0].source == "CLOSET"


@pytest.mark.asyncio
async def test_select_source_rejects_non_owner_or_missing_session():
    with pytest.raises(StyleSessionNotFound):
        await SelectClothingSourceUseCase(
            FakeStylingRepo(),
            FakeClosetRepo(),
            FakeAgentRun(),
        ).execute("user-123", str(uuid4()), ClothingSource.SHARED_CLOSET, UserPreference())


@pytest.mark.asyncio
async def test_select_candidates_persists_explicit_selection_and_triggers_generate():
    repo = FakeStylingRepo()
    session_id = uuid4()
    session = StyleSession(
        id=StyleSessionId(session_id),
        user_id="user-123",
        state=StyleSessionState.PROPOSING,
        clothing_source=ClothingSource.SHARED_CLOSET,
        shared_closet_id="adult-01",
        user_preference=UserPreference(gender="female"),
        proposed_candidates=[{"item_id": "item-1", "image_url": "http://item"}],
    )
    await repo.create(session)
    agent_run = FakeAgentRun()

    await SelectCandidatesUseCase(repo, agent_run).execute(
        "user-123", str(session_id), ["item-1"]
    )

    assert session.selected_items == [{"item_id": "item-1", "image_url": "http://item"}]
    assert agent_run.requests[0].phase == "generate"
    assert agent_run.requests[0].user_preference["gender"] == "female"


@pytest.mark.asyncio
async def test_select_candidates_rejects_when_daily_generation_limit_reached():
    repo = FakeStylingRepo()
    repo.completed_today_count = 5
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.PROPOSING,
            clothing_source=ClothingSource.SHARED_CLOSET,
            proposed_candidates=[{"item_id": "item-1"}],
        )
    )
    use_case = SelectCandidatesUseCase(
        repo,
        FakeAgentRun(),
        Settings(max_daily_generations_per_user=5),
    )

    with pytest.raises(DailyGenerationLimitExceeded, match="Daily generation limit of 5"):
        await use_case.execute("user-123", str(session_id), ["item-1"])


@pytest.mark.asyncio
async def test_select_candidates_allows_when_under_daily_generation_limit():
    repo = FakeStylingRepo()
    repo.completed_today_count = 4
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.PROPOSING,
            clothing_source=ClothingSource.SHARED_CLOSET,
            proposed_candidates=[{"item_id": "item-1"}],
        )
    )
    agent_run = FakeAgentRun()

    await SelectCandidatesUseCase(
        repo,
        agent_run,
        Settings(max_daily_generations_per_user=5),
    ).execute("user-123", str(session_id), ["item-1"])

    assert len(repo.count_completed_today_calls) == 1
    assert agent_run.requests[0].phase == "generate"


@pytest.mark.asyncio
async def test_select_candidates_skips_count_when_daily_generation_limit_unlimited():
    repo = FakeStylingRepo()
    repo.completed_today_count = 99
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.PROPOSING,
            clothing_source=ClothingSource.SHARED_CLOSET,
            proposed_candidates=[{"item_id": "item-1"}],
        )
    )
    agent_run = FakeAgentRun()

    await SelectCandidatesUseCase(
        repo,
        agent_run,
        Settings(max_daily_generations_per_user=0),
    ).execute("user-123", str(session_id), ["item-1"])

    assert repo.count_completed_today_calls == []
    assert agent_run.requests[0].phase == "generate"


@pytest.mark.asyncio
async def test_select_candidates_rejects_empty_or_unknown_selection():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.PROPOSING,
            clothing_source=ClothingSource.SHARED_CLOSET,
            proposed_candidates=[{"item_id": "item-1"}],
        )
    )
    use_case = SelectCandidatesUseCase(repo, FakeAgentRun())

    with pytest.raises(ValueError, match="At least one"):
        await use_case.execute("user-123", str(session_id), [])
    with pytest.raises(ValueError, match="Unknown candidate"):
        await use_case.execute("user-123", str(session_id), ["missing"])
