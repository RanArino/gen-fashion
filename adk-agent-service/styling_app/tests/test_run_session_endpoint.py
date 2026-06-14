import pytest
from fastapi.testclient import TestClient

from styling_app.server import RunSessionRequest, app, execute_run_session


class FakeRepo:
    def __init__(self):
        self.statuses = []
        self.events = []
        self.results = []
        self.errors = []

    async def update_status(self, session_id, status):
        self.statuses.append((session_id, status))

    async def write_event(self, session_id, event):
        self.events.append((session_id, event))

    async def write_style_result(self, session_id, style_result):
        self.results.append((session_id, style_result))

    async def mark_error(self, session_id, message):
        self.errors.append((session_id, message))


class FakeSessionService:
    def create_session(self, **kwargs):
        self.kwargs = kwargs


class FakeRunner:
    def __init__(self):
        self.session_service = FakeSessionService()

    async def run_async(self, **kwargs):
        yield type(
            "Event",
            (),
            {
                "author": "StylingAgent",
                "content": type(
                    "Content",
                    (),
                    {
                        "parts": [
                            type(
                                "Part",
                                (),
                                {
                                    "function_call": None,
                                    "function_response": type(
                                        "Response",
                                        (),
                                        {
                                            "model_dump": lambda self: {
                                                "name": "style_synthesizer",
                                                "response": {
                                                    "coordinate_image_url": "http://image",
                                                    "model_used": "collage-fallback",
                                                    "items": ["shirt"],
                                                },
                                            }
                                        },
                                    )(),
                                    "text": None,
                                    "thought_signature": None,
                                },
                            )()
                        ]
                    },
                )(),
            },
        )()


class EmptyRunner:
    def __init__(self):
        self.session_service = FakeSessionService()

    async def run_async(self, **kwargs):
        if False:
            yield None


class Settings:
    internal_task_secret = "s3cret"


def test_run_session_endpoint_returns_accepted(monkeypatch):
    async def fake_execute(request):
        return None

    monkeypatch.setattr("styling_app.server.execute_run_session", fake_execute)
    monkeypatch.setattr("styling_app.server.get_settings", lambda: Settings())
    client = TestClient(app)

    response = client.post(
        "/internal/run-session",
        headers={"X-Internal-Secret": "s3cret"},
        json={
            "sessionId": "session-1",
            "userId": "user-123",
            "source": "SHARED_CLOSET",
            "sharedClosetId": "adult-01",
            "userPreference": {"style": "clean"},
        },
    )

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "sessionId": "session-1"}


def test_run_session_endpoint_rejects_missing_or_wrong_secret(monkeypatch):
    monkeypatch.setattr("styling_app.server.get_settings", lambda: Settings())
    client = TestClient(app)
    payload = {
        "sessionId": "session-1",
        "userId": "user-123",
        "source": "SHARED_CLOSET",
        "sharedClosetId": "adult-01",
        "userPreference": {"style": "clean"},
    }

    assert client.post("/internal/run-session", json=payload).status_code == 403
    assert (
        client.post(
            "/internal/run-session",
            headers={"X-Internal-Secret": "wrong"},
            json=payload,
        ).status_code
        == 403
    )


def test_run_session_endpoint_locks_when_secret_unset(monkeypatch):
    class EmptySettings:
        internal_task_secret = None

    monkeypatch.setattr("styling_app.server.get_settings", lambda: EmptySettings())
    client = TestClient(app)

    response = client.post(
        "/internal/run-session",
        headers={"X-Internal-Secret": "anything"},
        json={
            "sessionId": "session-1",
            "userId": "user-123",
            "source": "SHARED_CLOSET",
            "sharedClosetId": "adult-01",
            "userPreference": {"style": "clean"},
        },
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_execute_run_session_writes_events_and_completion(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="adult-01",
        userPreference={"style": "clean"},
    )
    repo = FakeRepo()
    runner = FakeRunner()

    monkeypatch.setattr("styling_app.server.InMemorySessionService", lambda: runner.session_service)

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert repo.statuses[0] == ("session-1", "SEARCHING")
    assert repo.events[0][1]["eventKind"] == "thinking"
    assert repo.results == [
        (
            "session-1",
            {
                "coordinateImageUrl": "http://image",
                "items": ["shirt"],
                "modelUsed": "collage-fallback",
            },
        )
    ]
    assert repo.errors == []


@pytest.mark.asyncio
async def test_execute_run_session_falls_back_when_adk_has_no_result(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="adult-01",
        userPreference={"style": "clean", "colorPreference": "blue and white"},
    )
    repo = FakeRepo()
    runner = EmptyRunner()

    monkeypatch.setattr("styling_app.server.InMemorySessionService", lambda: runner.session_service)
    monkeypatch.setattr(
        "styling_app.server.search_closet",
        lambda **kwargs: [
            {
                "item_id": kwargs["category"],
                "image_url": f"http://image/{kwargs['category']}.jpg",
                "category": kwargs["category"],
            }
        ],
    )
    monkeypatch.setattr(
        "styling_app.server.style_synthesizer",
        lambda **kwargs: {
            "coordinate_image_url": "http://coordinate",
            "items": kwargs["item_image_urls"],
            "model_used": "collage-fallback",
        },
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert ("session-1", "GENERATING") in repo.statuses
    assert repo.results == [
        (
            "session-1",
            {
                "coordinateImageUrl": "http://coordinate",
                "items": ["http://image/top.jpg", "http://image/bottom.jpg"],
                "modelUsed": "collage-fallback",
                "selectedItems": [
                    {
                        "item_id": "top",
                        "image_url": "http://image/top.jpg",
                        "category": "top",
                    },
                    {
                        "item_id": "bottom",
                        "image_url": "http://image/bottom.jpg",
                        "category": "bottom",
                    },
                ],
            },
        )
    ]
    assert [event[1]["toolName"] for event in repo.events].count("search_closet") == 4
    assert repo.errors == []
