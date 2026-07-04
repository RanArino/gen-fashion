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
from app.domain.styling import CoordinationMode
from app.use_cases.styling import (
    AssistSessionUseCase,
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
async def test_select_source_closet_accepts_interesting_ready_item():
    from app.domain.closet import ClosetOwnershipStatus

    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )
    interesting = ready_item()
    interesting.set_ownership_status(ClosetOwnershipStatus.INTERESTING)
    agent_run = FakeAgentRun()

    await SelectClothingSourceUseCase(
        repo,
        FakeClosetRepo([interesting]),
        agent_run,
    ).execute("user-123", str(session_id), ClothingSource.CLOSET, UserPreference())

    assert agent_run.requests[0].source == "CLOSET"


@pytest.mark.asyncio
async def test_select_source_rejects_when_daily_generation_limit_reached_before_agent_run():
    repo = FakeStylingRepo()
    repo.completed_today_count = 5
    session_id = uuid4()
    await repo.create(
        StyleSession(
            id=StyleSessionId(session_id),
            user_id="user-123",
            state=StyleSessionState.SOURCE_SELECTING,
        )
    )
    agent_run = FakeAgentRun()

    with pytest.raises(DailyGenerationLimitExceeded, match="Daily generation limit of 5"):
        await SelectClothingSourceUseCase(
            repo,
            FakeClosetRepo(),
            agent_run,
            Settings(max_daily_generations_per_user=5),
        ).execute(
            "user-123",
            str(session_id),
            ClothingSource.SHARED_CLOSET,
            UserPreference(),
            "adult-01",
        )

    session = await repo.get_by_id("user-123", StyleSessionId(session_id))
    assert session.state == StyleSessionState.SOURCE_SELECTING
    assert len(repo.count_completed_today_calls) == 1
    assert agent_run.requests == []


@pytest.mark.asyncio
async def test_select_source_rejects_non_owner_or_missing_session():
    with pytest.raises(StyleSessionNotFound):
        await SelectClothingSourceUseCase(
            FakeStylingRepo(),
            FakeClosetRepo(),
            FakeAgentRun(),
        ).execute("user-123", str(uuid4()), ClothingSource.SHARED_CLOSET, UserPreference())


class FakeImageStorage:
    async def get_download_url(self, image_path):
        return f"http://storage/{image_path}?sig=abc"


def assist_use_case(repo, closet_repo, agent_run, settings=None):
    return AssistSessionUseCase(
        repo, closet_repo, FakeImageStorage(), agent_run, settings or Settings()
    )


def source_selecting_session(session_id, user_id="user-123"):
    return StyleSession(
        id=StyleSessionId(session_id),
        user_id=user_id,
        state=StyleSessionState.SOURCE_SELECTING,
    )


@pytest.mark.asyncio
async def test_assist_session_stores_assisted_mode_and_triggers_agent():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    anchor = ready_item()
    agent_run = FakeAgentRun()

    result = await assist_use_case(repo, FakeClosetRepo([anchor]), agent_run).execute(
        "user-123",
        str(session_id),
        [str(anchor.id)],
        UserPreference(style="clean", gender="female"),
    )

    session = await repo.get_by_id("user-123", StyleSessionId(session_id))
    assert result.status == "SEARCHING"
    assert result.source == "CLOSET"
    assert session.coordination_mode == CoordinationMode.ASSISTED
    assert session.anchor_items[0]["item_id"] == str(anchor.id)
    assert session.anchor_items[0]["anchor"] is True
    assert session.anchor_items[0]["recommended"] is True
    assert session.anchor_items[0]["image_url"].startswith("http://storage/")
    request = agent_run.requests[0]
    assert request.phase == "propose"
    assert request.mode == "assisted"
    assert request.source == "CLOSET"
    assert request.anchor_items == session.anchor_items
    assert request.user_preference["gender"] == "female"


@pytest.mark.asyncio
async def test_assist_session_rejects_zero_and_four_anchors():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    use_case = assist_use_case(repo, FakeClosetRepo(), FakeAgentRun())

    with pytest.raises(ValueError, match="1 to 3"):
        await use_case.execute("user-123", str(session_id), [], UserPreference())
    with pytest.raises(ValueError, match="1 to 3"):
        await use_case.execute(
            "user-123", str(session_id), [str(uuid4()) for _ in range(4)], UserPreference()
        )


@pytest.mark.asyncio
async def test_assist_session_rejects_missing_and_non_ready_anchors():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    processing = ready_item()
    object.__setattr__(processing, "status", ClothingItemStatus.PROCESSING)
    use_case = assist_use_case(repo, FakeClosetRepo([processing]), FakeAgentRun())

    with pytest.raises(ValueError, match="not found in your closet"):
        await use_case.execute("user-123", str(session_id), [str(uuid4())], UserPreference())
    with pytest.raises(ValueError, match="not READY"):
        await use_case.execute(
            "user-123", str(session_id), [str(processing.id)], UserPreference()
        )


@pytest.mark.asyncio
async def test_assist_session_rejects_other_users_anchor():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    other_users_item = ready_item(user_id="other-user")
    use_case = assist_use_case(repo, FakeClosetRepo([other_users_item]), FakeAgentRun())

    with pytest.raises(ValueError, match="not found in your closet"):
        await use_case.execute(
            "user-123", str(session_id), [str(other_users_item.id)], UserPreference()
        )


@pytest.mark.asyncio
async def test_assist_session_rejects_non_owner_or_missing_session():
    with pytest.raises(StyleSessionNotFound):
        await assist_use_case(FakeStylingRepo(), FakeClosetRepo(), FakeAgentRun()).execute(
            "user-123", str(uuid4()), [str(uuid4())], UserPreference()
        )


@pytest.mark.asyncio
async def test_assist_session_enforces_daily_generation_limit_before_agent_run():
    repo = FakeStylingRepo()
    repo.completed_today_count = 5
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    anchor = ready_item()
    agent_run = FakeAgentRun()

    with pytest.raises(DailyGenerationLimitExceeded):
        await assist_use_case(
            repo,
            FakeClosetRepo([anchor]),
            agent_run,
            Settings(max_daily_generations_per_user=5),
        ).execute("user-123", str(session_id), [str(anchor.id)], UserPreference())

    session = await repo.get_by_id("user-123", StyleSessionId(session_id))
    assert session.state == StyleSessionState.SOURCE_SELECTING
    assert agent_run.requests == []


@pytest.mark.asyncio
async def test_assist_session_marks_error_when_agent_trigger_fails():
    repo = FakeStylingRepo()
    session_id = uuid4()
    await repo.create(source_selecting_session(session_id))
    anchor = ready_item()

    with pytest.raises(RuntimeError, match="Failed to start assisted styling run"):
        await assist_use_case(repo, FakeClosetRepo([anchor]), FailingAgentRun()).execute(
            "user-123", str(session_id), [str(anchor.id)], UserPreference()
        )

    session = await repo.get_by_id("user-123", StyleSessionId(session_id))
    assert session.state == StyleSessionState.ERROR


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
