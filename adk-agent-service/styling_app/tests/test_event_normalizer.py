from dataclasses import dataclass
from datetime import datetime, timezone

from styling_app.events import (
    extract_search_candidates,
    extract_style_result,
    normalize_adk_event,
)


@dataclass
class FunctionCall:
    name: str
    args: dict

    def model_dump(self):
        return {"name": self.name, "args": self.args}


@dataclass
class FunctionResponse:
    name: str
    response: dict

    def model_dump(self):
        return {"name": self.name, "response": self.response}


@dataclass
class Part:
    function_call: FunctionCall | None = None
    function_response: FunctionResponse | None = None
    text: str | None = None
    thought_signature: bytes | None = None


@dataclass
class Content:
    parts: list[Part]


@dataclass
class Event:
    author: str
    content: Content


def test_normalizes_function_call_response_and_final_answer():
    now = datetime(2026, 6, 12, tzinfo=timezone.utc)

    call_events = normalize_adk_event(
        Event("ClosetAgent", Content([Part(function_call=FunctionCall("search_closet", {"source": "SHARED_CLOSET"}), thought_signature=b"abc")])),
        3,
        now,
    )
    result_events = normalize_adk_event(
        Event("StylingAgent", Content([Part(function_response=FunctionResponse("style_synthesizer", {"coordinate_image_url": "http://image", "model_used": "collage-fallback"}))])),
        4,
        now,
    )
    text_events = normalize_adk_event(Event("StylingAgent", Content([Part(text="Done")])), 5, now)

    assert call_events[0]["eventKind"] == "tool_call"
    assert call_events[0]["toolName"] == "search_closet"
    assert call_events[0]["thoughtSignature"] == "YWJj"
    assert result_events[0]["eventKind"] == "tool_result"
    assert extract_style_result(result_events[0]) == {
        "coordinateImageUrl": "http://image",
        "items": [],
        "modelUsed": "collage-fallback",
    }
    assert text_events[0]["eventKind"] == "final_answer"
    assert text_events[0]["text"] == "Done"


def test_extracts_search_candidates_from_normalized_tool_result():
    result_events = normalize_adk_event(
        Event(
            "ClosetAgent",
            Content(
                [
                    Part(
                        function_response=FunctionResponse(
                            "search_closet",
                            {"result": [{"item_id": "item-1", "image_url": "http://item"}]},
                        )
                    )
                ]
            ),
        ),
        1,
    )

    assert extract_search_candidates(result_events[0]) == [
        {"item_id": "item-1", "image_url": "http://item"}
    ]


def test_native_transfer_call_is_kept_once_without_action_duplicate():
    event = Event(
        "styling_app",
        Content(
            [
                Part(
                    function_call=FunctionCall(
                        "transfer_to_agent", {"agent_name": "ClosetAgent"}
                    )
                )
            ]
        ),
    )
    event.actions = type("Actions", (), {"transfer_to_agent": "ClosetAgent"})()

    normalized = normalize_adk_event(event, 1)

    assert len(normalized) == 1
    assert normalized[0]["toolName"] == "transfer_to_agent"
    assert normalized[0]["toolArgs"] == {"agent_name": "ClosetAgent"}
