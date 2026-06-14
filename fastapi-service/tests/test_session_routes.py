from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import verify_firebase_token
from app.dependencies import get_create_session_use_case, get_select_source_use_case, get_styling_repository
from app.domain.styling import StyleSessionNotFound
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
