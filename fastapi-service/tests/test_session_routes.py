from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import verify_firebase_token
from app.dependencies import (
    get_create_session_use_case,
    get_select_candidates_use_case,
    get_select_source_use_case,
    get_styling_repository,
)
from app.domain.styling import (
    ClothingSource,
    StyleResult,
    StyleSession,
    StyleSessionId,
    StyleSessionNotFound,
    StyleSessionState,
)
from app.domain.styling.exceptions import DailyGenerationLimitExceeded
from app.main import app


def reset_overrides():
    app.dependency_overrides = {}


class CreateUseCase:
    async def execute(self, user_id):
        return type(
            "Result",
            (),
            {"session_id": "session-1", "status": "SOURCE_SELECTING", "source": "UNSET"},
        )()


class SelectUseCase:
    def __init__(self, error=None):
        self.error = error

    async def execute(self, **kwargs):
        if self.error:
            raise self.error
        return type(
            "Result",
            (),
            {"session_id": kwargs["session_id"], "status": "SEARCHING", "source": kwargs["source"].value},
        )()


class FailingSelectUseCase:
    async def execute(self, **kwargs):
        from app.use_cases.styling import AgentRunStartFailed

        raise AgentRunStartFailed("Failed to start styling run")


class SelectCandidatesRouteUseCase:
    async def execute(self, user_id, session_id, selected_item_ids):
        assert selected_item_ids == ["item-1"]
        return type(
            "Result",
            (),
            {"session_id": session_id, "status": "PROPOSING", "source": "SHARED_CLOSET"},
        )()


class DailyLimitSelectCandidatesRouteUseCase:
    async def execute(self, user_id, session_id, selected_item_ids):
        raise DailyGenerationLimitExceeded(
            "Daily generation limit of 5 reached. Limit resets at midnight UTC."
        )


class DailyLimitSelectSourceRouteUseCase:
    async def execute(self, **kwargs):
        raise DailyGenerationLimitExceeded(
            "Daily generation limit of 5 reached. Limit resets at midnight UTC."
        )


class StreamRepo:
    def __init__(self, session=None):
        self.session = session

    async def get_by_id(self, user_id, session_id):
        return self.session

    async def list_events(self, user_id, session_id, after_seq=0):
        if after_seq >= 1:
            return []
        return [{"seq": 1, "agentName": "ClosetAgent", "eventKind": "tool_call"}]


class TerminalRaceRepo:
    def __init__(self):
        self.calls = 0

    async def get_by_id(self, user_id, session_id):
        return StreamSession()

    async def list_events(self, user_id, session_id, after_seq=0):
        self.calls += 1
        if self.calls == 1:
            return []
        return [
            {
                "seq": 2,
                "agentName": "StylingAgent",
                "eventKind": "tool_result",
                "toolName": "style_synthesizer",
                "toolResult": {"coordinateImageUrl": "http://image"},
            }
        ]


class StreamSession:
    state = type("State", (), {"value": "COMPLETED"})()
    clothing_source = type("Source", (), {"value": "SHARED_CLOSET"})()


class ProposedSession:
    state = type("State", (), {"value": "PROPOSING"})()
    clothing_source = type("Source", (), {"value": "SHARED_CLOSET"})()
    selected_items = []
    proposed_candidates = [{"item_id": "item-1"}]


class HistoryRepo:
    def __init__(self, sessions):
        self.sessions = sessions
        self.request = None

    async def get_by_id(self, user_id, session_id):
        self.request = (user_id, session_id)
        for session in self.sessions:
            if session.id == session_id and session.user_id == user_id:
                return session
        return None

    async def list_completed(self, user_id, limit=20):
        self.request = (user_id, limit)
        return self.sessions


def _completed_session(image_url: str, session_id: StyleSessionId | None = None) -> StyleSession:
    completed_at = datetime(2026, 6, 24, 10, 32)
    return StyleSession(
        id=session_id or StyleSessionId(uuid4()),
        user_id="user-123",
        state=StyleSessionState.COMPLETED,
        clothing_source=ClothingSource.SHARED_CLOSET,
        shared_closet_id="adult-01",
        selected_items=[
            {
                "item_id": "item-1",
                "image_url": "https://example.test/item.jpg",
                "category": "top",
                "gender": "common",
            }
        ],
        final_result=StyleResult(coordinate_image_url=image_url),
        created_at=datetime(2026, 6, 24, 10, 30),
        completed_at=completed_at,
    )


def test_create_session_requires_auth():
    reset_overrides()
    client = TestClient(app)

    response = client.post("/sessions")

    assert response.status_code == 401


def test_create_session_returns_source_selecting():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_create_session_use_case] = lambda: CreateUseCase()
    client = TestClient(app)

    response = client.post("/sessions")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "status": "SOURCE_SELECTING",
        "source": "UNSET",
    }
    reset_overrides()


def test_list_sessions_returns_200_with_completed_sessions():
    reset_overrides()
    repo = HistoryRepo(
        [
            _completed_session("https://example.test/first.jpg"),
            _completed_session("https://example.test/second.jpg"),
        ]
    )
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: repo

    response = TestClient(app).get("/sessions?limit=2")

    assert response.status_code == 200
    assert repo.request == ("user-123", 2)
    assert [item["style_result"]["coordinate_image_url"] for item in response.json()] == [
        "https://example.test/first.jpg",
        "https://example.test/second.jpg",
    ]
    assert response.json()[0]["selected_items"][0]["item_id"] == "item-1"
    reset_overrides()


def test_list_sessions_empty_when_no_completed():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: HistoryRepo([])

    response = TestClient(app).get("/sessions")

    assert response.status_code == 200
    assert response.json() == []
    reset_overrides()


def test_get_session_returns_current_session_state():
    reset_overrides()
    session_id = StyleSessionId(uuid4())
    session = _completed_session("https://example.test/result.jpg", session_id)
    session.proposed_candidates = [{"item_id": "candidate-1"}]
    repo = HistoryRepo([session])
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: repo

    response = TestClient(app).get(f"/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert response.json()["proposed_candidates"] == [{"item_id": "candidate-1"}]
    assert (
        response.json()["style_result"]["coordinate_image_url"]
        == "https://example.test/result.jpg"
    )
    reset_overrides()


def test_get_session_returns_404_for_missing_or_unowned_session():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: HistoryRepo([])

    response = TestClient(app).get(f"/sessions/{uuid4()}")

    assert response.status_code == 404
    reset_overrides()


def test_select_source_accepts_shared_closet():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_source_use_case] = lambda: SelectUseCase()
    client = TestClient(app)

    response = client.post(
        f"/sessions/{session_id}/source",
        json={
            "source": "SHARED_CLOSET",
            "sharedClosetId": "adult-01",
            "userPreference": {"occasion": "work", "colorPreference": "blue"},
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "session_id": session_id,
        "status": "SEARCHING",
        "source": "SHARED_CLOSET",
    }
    reset_overrides()


def test_select_source_maps_invalid_source_and_missing_session():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_source_use_case] = lambda: SelectUseCase(
        ValueError("RAKUTEN is not available")
    )
    client = TestClient(app)

    assert client.post(
        f"/sessions/{session_id}/source",
        json={"source": "RAKUTEN", "userPreference": {}},
    ).status_code == 400

    app.dependency_overrides[get_select_source_use_case] = lambda: SelectUseCase(
        StyleSessionNotFound("missing")
    )
    assert client.post(
        f"/sessions/{session_id}/source",
        json={"source": "SHARED_CLOSET", "userPreference": {}},
    ).status_code == 404
    reset_overrides()


def test_select_source_maps_agent_trigger_failure():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_source_use_case] = lambda: FailingSelectUseCase()
    client = TestClient(app)

    response = client.post(
        f"/sessions/{session_id}/source",
        json={"source": "SHARED_CLOSET", "userPreference": {}},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to start styling run"
    reset_overrides()


def test_select_source_returns_429_when_daily_generation_limit_reached():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_source_use_case] = (
        lambda: DailyLimitSelectSourceRouteUseCase()
    )
    client = TestClient(app)

    response = client.post(
        f"/sessions/{session_id}/source",
        json={"source": "SHARED_CLOSET", "userPreference": {}},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Daily generation limit of 5 reached. Limit resets at midnight UTC."
    )
    reset_overrides()


def test_select_candidates_accepts_explicit_selection():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_candidates_use_case] = (
        lambda: SelectCandidatesRouteUseCase()
    )
    response = TestClient(app).post(
        f"/sessions/{session_id}/select",
        json={"selectedItemIds": ["item-1"]},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "PROPOSING"
    reset_overrides()


def test_select_candidates_returns_429_when_daily_generation_limit_reached():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_select_candidates_use_case] = (
        lambda: DailyLimitSelectCandidatesRouteUseCase()
    )
    response = TestClient(app).post(
        f"/sessions/{session_id}/select",
        json={"selectedItemIds": ["item-1"]},
    )

    assert response.status_code == 429
    assert response.json()["detail"] == (
        "Daily generation limit of 5 reached. Limit resets at midnight UTC."
    )
    reset_overrides()


def test_stream_requires_ownership_and_returns_sse_backfill():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: StreamRepo(None)
    client = TestClient(app)

    assert client.get(f"/sessions/{session_id}/stream").status_code == 404

    app.dependency_overrides[get_styling_repository] = lambda: StreamRepo(StreamSession())
    response = client.get(f"/sessions/{session_id}/stream")

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: session.snapshot" in response.text
    assert "event: agent.event" in response.text
    assert "event: session.completed" in response.text
    reset_overrides()


def test_stream_drains_events_after_terminal_status_race():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: TerminalRaceRepo()
    client = TestClient(app)

    response = client.get(f"/sessions/{session_id}/stream")

    assert response.status_code == 200
    assert "style_synthesizer" in response.text
    assert "coordinateImageUrl" in response.text
    assert response.text.index("style_synthesizer") < response.text.index("session.completed")
    reset_overrides()


def test_stream_emits_proposed_candidates_and_closes():
    reset_overrides()
    session_id = str(uuid4())
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_styling_repository] = lambda: StreamRepo(ProposedSession())

    response = TestClient(app).get(f"/sessions/{session_id}/stream")

    assert response.status_code == 200
    assert "event: session.proposed" in response.text
    assert '"item_id": "item-1"' in response.text
    reset_overrides()
