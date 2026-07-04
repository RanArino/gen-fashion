import inspect
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from styling_app.server import (
    RunSessionRequest,
    _build_generate_style_tool,
    _build_propose_search_tool,
    app,
    execute_run_session,
)


class FakeRepo:
    def __init__(self, next_seq=1):
        self.statuses = []
        self.events = []
        self.results = []
        self.errors = []
        self.proposals = []
        self.next_seq_value = next_seq

    async def next_seq(self, session_id):
        return self.next_seq_value

    async def get_closet_kind(self, closet_id):
        return "child" if closet_id.startswith("child-") else "adult"

    async def write_proposed_candidates(self, session_id, candidates):
        self.proposals.append((session_id, candidates))

    async def update_status(self, session_id, status):
        self.statuses.append((session_id, status))

    async def write_event(self, session_id, event):
        self.events.append((session_id, event))

    async def write_style_result(self, session_id, style_result):
        self.results.append((session_id, style_result))

    async def mark_error(self, session_id, message):
        self.errors.append((session_id, message))


class Settings:
    internal_task_secret = "s3cret"


class FakeRunner:
    def __init__(self, events):
        self.events = events
        self.kwargs = None

    async def run_async(self, **kwargs):
        self.kwargs = kwargs
        for event in self.events:
            yield event


def _adk_event(author, *, call=None, response=None, text=None):
    part = {
        "function_call": call,
        "function_response": response,
        "text": text,
        "thought_signature": None,
    }
    return SimpleNamespace(
        author=author,
        content=SimpleNamespace(parts=[part]),
    )


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
async def test_propose_phase_runs_agent_and_stops_without_generation(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="adult-01",
        userPreference={"style": "clean", "gender": "female"},
    )
    repo = FakeRepo(next_seq=7)
    description = "lightweight indigo overshirt with a relaxed spring silhouette"
    runner = FakeRunner(
        [
            _adk_event(
                "styling_app",
                call={
                    "name": "transfer_to_agent",
                    "args": {"agent_name": "ClosetAgent"},
                },
            ),
            _adk_event(
                "ClosetAgent",
                call={
                    "name": "search_closet",
                    "args": {
                        "description": description,
                        "source": "SHARED_CLOSET",
                        "user_id": "user-123",
                        "shared_closet_id": "adult-01",
                    },
                },
            ),
            _adk_event(
                "ClosetAgent",
                response={
                    "name": "search_closet",
                    "response": {
                        "result": [
                            {
                                "item_id": "item-1",
                                "image_url": "http://item",
                                "category": "Blouse",
                            }
                        ]
                    },
                },
            ),
            _adk_event("ClosetAgent", text="Candidate search complete."),
        ]
    )
    monkeypatch.setattr(
        "styling_app.server.search_closet",
        lambda **kwargs: pytest.fail("fallback search must not run"),
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert repo.statuses[0] == ("session-1", "SEARCHING")
    assert repo.proposals == [
        (
            "session-1",
            [
                {
                    "item_id": "item-1",
                    "image_url": "http://item",
                    "category": "Blouse",
                }
            ],
        )
    ]
    assert repo.results == []
    assert repo.errors == []
    assert [event[1]["seq"] for event in repo.events] == [7, 8, 9, 10]
    assert repo.events[0][1]["toolName"] == "transfer_to_agent"
    assert repo.events[1][1]["toolArgs"]["description"] == description
    assert repo.events[1][1]["toolArgs"]["gender"] == "female"
    assert all(event[1]["toolName"] != "style_synthesizer" for event in repo.events)
    assert '"gender":"female"' in runner.kwargs["new_message"].parts[0].text


ANCHOR = {
    "item_id": "anchor-1",
    "source": "CLOSET",
    "image_url": "http://storage/anchor-1.jpg",
    "anchor": True,
    "recommended": True,
}


def _assisted_request():
    return RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="CLOSET",
        userPreference={"style": "clean", "gender": "female", "colorPreference": "white"},
        mode="assisted",
        anchorItems=[ANCHOR],
    )


@pytest.mark.asyncio
async def test_assisted_propose_merges_anchors_with_rakuten_candidates(monkeypatch):
    request = _assisted_request()
    repo = FakeRepo()
    runner = FakeRunner(
        [
            _adk_event(
                "ClosetAgent",
                response={
                    "name": "search_rakuten",
                    "response": {
                        "result": [
                            {
                                "item_id": "rakuten:shop:1",
                                "source": "RAKUTEN",
                                "name": "White T-Shirt",
                                "image_url": "http://thumb/1.jpg",
                                "price": 2980,
                                "external_url": "http://item/1",
                            }
                        ]
                    },
                },
            ),
            _adk_event("ClosetAgent", text="Suggestions ready."),
        ]
    )
    monkeypatch.setattr(
        "styling_app.server.search_rakuten",
        lambda **kwargs: pytest.fail("rakuten fallback must not run"),
    )
    monkeypatch.setattr(
        "styling_app.server.search_closet",
        lambda **kwargs: pytest.fail("closet fallback must not run"),
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert repo.errors == []
    candidates = repo.proposals[0][1]
    assert candidates[0]["item_id"] == "anchor-1"
    assert candidates[0]["anchor"] is True
    assert candidates[0]["recommended"] is True
    assert candidates[1]["item_id"] == "rakuten:shop:1"
    assert candidates[1]["recommended"] is True
    message = runner.kwargs["new_message"].parts[0].text
    assert '"mode":"assisted"' in message
    assert '"anchorItems":[{' in message


@pytest.mark.asyncio
async def test_assisted_propose_runs_rakuten_fallback_when_agent_has_no_suggestions(
    monkeypatch,
):
    request = _assisted_request()
    repo = FakeRepo()
    runner = FakeRunner([_adk_event("styling_app", text="No suggestions.")])
    captured = {}

    def fake_search_rakuten(**kwargs):
        captured.update(kwargs)
        return [
            {
                "item_id": "rakuten:fb:1",
                "source": "RAKUTEN",
                "image_url": "http://thumb/fb.jpg",
            }
        ]

    monkeypatch.setattr("styling_app.server.search_rakuten", fake_search_rakuten)

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert captured["query"] == "clean white"
    assert captured["colors"] == ["white"]
    candidates = repo.proposals[0][1]
    assert [c["item_id"] for c in candidates] == ["anchor-1", "rakuten:fb:1"]
    assert candidates[1]["recommended"] is True


def test_propose_rakuten_tool_returns_empty_when_unavailable(monkeypatch):
    from styling_app.adapters.rakuten import RakutenUnavailableError
    from styling_app.server import _build_propose_rakuten_tool

    def unavailable(**kwargs):
        raise RakutenUnavailableError("403")

    monkeypatch.setattr("styling_app.server.search_rakuten", unavailable)
    tool = _build_propose_rakuten_tool()

    assert tool(query="white t-shirt") == []


@pytest.mark.asyncio
async def test_assisted_propose_degrades_to_anchors_when_rakuten_unavailable(monkeypatch):
    from styling_app.adapters.rakuten import RakutenUnavailableError

    request = _assisted_request()
    repo = FakeRepo()
    runner = FakeRunner([_adk_event("styling_app", text="No suggestions.")])

    def unavailable(**kwargs):
        raise RakutenUnavailableError("no credentials")

    monkeypatch.setattr("styling_app.server.search_rakuten", unavailable)

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert repo.errors == []
    candidates = repo.proposals[0][1]
    assert [c["item_id"] for c in candidates] == ["anchor-1"]
    assert any(
        (event[1]["text"] or "").startswith("Rakuten suggestions unavailable")
        for event in repo.events
    )


@pytest.mark.asyncio
async def test_generate_phase_runs_agent_with_selection_gender_and_child_age(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={
            "style": "clean",
            "colorPreference": "blue and white",
            "gender": "female",
        },
        phase="generate",
        selectedItems=[
            {"item_id": "top", "image_url": "http://image/top.jpg", "category": "top"},
            {"item_id": "bottom", "image_url": "http://image/bottom.jpg", "category": "bottom"},
        ],
    )
    repo = FakeRepo(next_seq=11)
    synth_args = {
        "user_id": "user-123",
        "item_image_urls": ["http://image/top.jpg", "http://image/bottom.jpg"],
        "style_description": "clean blue and white",
        "gender": "female",
        "wearer_age": "child",
        "language": "ja",
    }
    runner = FakeRunner(
        [
            _adk_event(
                "StylingAgent",
                call={"name": "style_synthesizer", "args": synth_args},
            ),
            _adk_event(
                "StylingAgent",
                response={
                    "name": "style_synthesizer",
                    "response": {
                        "coordinate_image_url": "http://coordinate",
                        "items": synth_args["item_image_urls"],
                        "model_used": "gemini-2.5-flash-image",
                        "generation_prompt": "Outfit worn by a child female wearer.",
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr(
        "styling_app.server.style_synthesizer",
        lambda **kwargs: pytest.fail("generation fallback must not run"),
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert ("session-1", "GENERATING") in repo.statuses
    assert repo.results == [
        (
            "session-1",
            {
                "coordinateImageUrl": "http://coordinate",
                "items": ["http://image/top.jpg", "http://image/bottom.jpg"],
                "modelUsed": "gemini-2.5-flash-image",
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
    assert [event[1]["toolName"] for event in repo.events].count("search_closet") == 0
    assert [event[1]["seq"] for event in repo.events] == [11, 12]
    assert repo.events[0][1]["toolArgs"] == synth_args
    message = runner.kwargs["new_message"].parts[0].text
    assert '"gender":"female"' in message
    assert '"wearerAge":"child"' in message
    assert '"language":"ja"' in message
    assert repo.errors == []


@pytest.mark.asyncio
async def test_propose_phase_uses_search_fallback_only_when_agent_returns_no_candidates(
    monkeypatch,
):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="adult-01",
        userPreference={"style": "clean", "gender": "common"},
    )
    repo = FakeRepo()
    runner = FakeRunner([_adk_event("styling_app", text="No matches found.")])
    monkeypatch.setattr(
        "styling_app.server.search_closet",
        lambda **kwargs: [
            {"item_id": kwargs["category"], "image_url": "http://item"}
        ],
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert len(repo.proposals[0][1]) == 2
    assert any(
        event[1]["text"] == "Agent returned no candidates; running search fallback"
        for event in repo.events
    )
    assert all(event[1]["toolName"] != "style_synthesizer" for event in repo.events)


@pytest.mark.asyncio
async def test_generate_phase_falls_back_only_after_explicit_selection(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={"style": "clean", "gender": "common"},
        phase="generate",
        selectedItems=[
            {"item_id": "top", "image_url": "http://image/top.jpg"},
        ],
    )
    repo = FakeRepo()
    runner = FakeRunner([_adk_event("StylingAgent", text="Unable to generate.")])
    captured = {}

    def fake_synthesizer(**kwargs):
        captured.update(kwargs)
        return {
            "coordinate_image_url": "http://coordinate",
            "items": kwargs["item_image_urls"],
            "model_used": "collage-fallback",
        }

    monkeypatch.setattr("styling_app.server.style_synthesizer", fake_synthesizer)

    await execute_run_session(request, session_repo=repo, runner=runner)

    assert captured["item_image_urls"] == ["http://image/top.jpg"]
    assert captured["gender"] == "common"
    assert captured["wearer_age"] == "child"
    assert captured["language"] == "ja"
    assert repo.results[0][1]["coordinateImageUrl"] == "http://coordinate"


def test_generate_style_tool_exposes_only_style_description(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="owner-1",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={"style": "clean", "colorPreference": "blue", "gender": "female"},
        phase="generate",
        selectedItems=[
            {"item_id": "top", "image_url": "http://image/top.jpg"},
            {"item_id": "bottom", "image_url": "http://image/bottom.jpg"},
        ],
    )
    captured = {}

    def fake_synthesizer(**kwargs):
        captured.update(kwargs)
        return {"coordinate_image_url": "http://coordinate", "items": kwargs["item_image_urls"]}

    monkeypatch.setattr("styling_app.server.style_synthesizer", fake_synthesizer)
    tool = _build_generate_style_tool(request, "female", "child", "en")

    params = list(inspect.signature(tool).parameters)
    assert params == ["style_description"]

    tool(style_description="breezy summer look")

    assert captured["user_id"] == "owner-1"
    assert captured["item_image_urls"] == ["http://image/top.jpg", "http://image/bottom.jpg"]
    assert captured["style_description"] == "breezy summer look"
    assert captured["gender"] == "female"
    assert captured["wearer_age"] == "child"
    assert captured["language"] == "en"


def test_generate_style_tool_defaults_empty_style_to_preference(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="owner-1",
        source="SHARED_CLOSET",
        sharedClosetId="adult-01",
        userPreference={"style": "minimal", "colorPreference": "earth tones"},
        phase="generate",
        selectedItems=[{"item_id": "top", "image_url": "http://image/top.jpg"}],
    )
    captured = {}

    def fake_synthesizer(**kwargs):
        captured.update(kwargs)
        return {"coordinate_image_url": "http://coordinate", "items": kwargs["item_image_urls"]}

    monkeypatch.setattr("styling_app.server.style_synthesizer", fake_synthesizer)
    tool = _build_generate_style_tool(request, "common", "adult", "ja")

    tool(style_description="   ")

    assert captured["style_description"] == "minimal earth tones"
    assert captured["language"] == "ja"


@pytest.mark.asyncio
async def test_generate_trace_and_result_normalize_to_server_values(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={"style": "clean", "colorPreference": "blue", "gender": "female"},
        phase="generate",
        selectedItems=[
            {"item_id": "top", "image_url": "http://image/top.jpg"},
            {"item_id": "bottom", "image_url": "http://image/bottom.jpg"},
        ],
    )
    repo = FakeRepo(next_seq=20)
    # The LLM-side event claims adult, foreign URLs, and a different user_id.
    runner = FakeRunner(
        [
            _adk_event(
                "StylingAgent",
                call={
                    "name": "style_synthesizer",
                    "args": {
                        "user_id": "attacker",
                        "item_image_urls": ["http://evil/other.jpg"],
                        "style_description": "edgy",
                        "gender": "male",
                        "wearer_age": "adult",
                    },
                },
            ),
            _adk_event(
                "StylingAgent",
                response={
                    "name": "style_synthesizer",
                    "response": {
                        "coordinate_image_url": "http://coordinate",
                        "items": ["http://evil/other.jpg"],
                        "model_used": "gemini-2.5-flash-image",
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr(
        "styling_app.server.style_synthesizer",
        lambda **kwargs: pytest.fail("generation fallback must not run"),
    )

    await execute_run_session(request, session_repo=repo, runner=runner)

    tool_call = repo.events[0][1]
    assert tool_call["toolName"] == "style_synthesizer"
    assert tool_call["toolArgs"] == {
        "user_id": "user-123",
        "item_image_urls": ["http://image/top.jpg", "http://image/bottom.jpg"],
        "style_description": "edgy",
        "gender": "female",
        "wearer_age": "child",
        "language": "ja",
    }
    saved = repo.results[0][1]
    assert saved["items"] == ["http://image/top.jpg", "http://image/bottom.jpg"]
    assert saved["coordinateImageUrl"] == "http://coordinate"
    assert saved["selectedItems"] == request.selected_items
    assert repo.errors == []


@pytest.mark.asyncio
async def test_generate_missing_image_url_errors_without_running(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="user-123",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={"style": "clean"},
        phase="generate",
        selectedItems=[
            {"item_id": "top", "image_url": "http://image/top.jpg"},
            {"item_id": "bottom"},
        ],
    )
    repo = FakeRepo()

    class ExplodingRunner:
        async def run_async(self, **kwargs):
            pytest.fail("Runner must not start when a selection lacks an image")
            yield  # pragma: no cover

    monkeypatch.setattr(
        "styling_app.server.style_synthesizer",
        lambda **kwargs: pytest.fail("generation fallback must not run"),
    )

    await execute_run_session(request, session_repo=repo, runner=ExplodingRunner())

    assert repo.statuses == []
    assert repo.results == []
    assert repo.errors == [("session-1", "Selected items have no images")]


def test_propose_search_tool_binds_authoritative_context(monkeypatch):
    request = RunSessionRequest(
        sessionId="session-1",
        userId="owner-1",
        source="SHARED_CLOSET",
        sharedClosetId="child-01",
        userPreference={"gender": "female"},
    )
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr("styling_app.server.search_closet", fake_search)
    tool = _build_propose_search_tool(request, "female")

    tool(
        description="blue child shirt",
        source="CLOSET",
        user_id="another-user",
        shared_closet_id="adult-02",
        gender="male",
    )

    assert captured["source"] == "SHARED_CLOSET"
    assert captured["user_id"] == "owner-1"
    assert captured["shared_closet_id"] == "child-01"
    assert captured["gender"] == "female"
