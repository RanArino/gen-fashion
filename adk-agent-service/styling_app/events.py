import base64
from datetime import datetime, timedelta, timezone
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _encode_signature(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, str):
        return value
    return base64.b64encode(bytes(value)).decode("ascii")


def _part_value(part: Any, name: str) -> Any:
    if isinstance(part, dict):
        return part.get(name)
    return getattr(part, name, None)


def normalize_adk_event(event: Any, seq_start: int, created_at: datetime | None = None) -> list[dict]:
    """Normalize an ADK Event into Firestore-friendly UI events."""
    created_at = created_at or datetime.now(timezone.utc)
    ttl_at = created_at + timedelta(hours=24)
    author = getattr(event, "author", None) or "unknown"
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    events: list[dict[str, Any]] = []
    seq = seq_start

    for part in parts:
        function_call = _part_value(part, "function_call")
        function_response = _part_value(part, "function_response")
        text = _part_value(part, "text")
        thought_signature = _part_value(part, "thought_signature")

        if function_call is not None:
            call = _as_dict(function_call)
            events.append(
                {
                    "seq": seq,
                    "agentName": author,
                    "eventKind": "tool_call",
                    "toolName": call.get("name"),
                    "toolArgs": call.get("args") or {},
                    "toolResult": None,
                    "text": None,
                    "a2uiPayload": None,
                    "thoughtSignature": _encode_signature(thought_signature),
                    "createdAt": created_at,
                    "ttlAt": ttl_at,
                }
            )
            seq += 1
        elif function_response is not None:
            response = _as_dict(function_response)
            events.append(
                {
                    "seq": seq,
                    "agentName": author,
                    "eventKind": "tool_result",
                    "toolName": response.get("name"),
                    "toolArgs": None,
                    "toolResult": response.get("response") or {},
                    "text": None,
                    "a2uiPayload": None,
                    "thoughtSignature": _encode_signature(thought_signature),
                    "createdAt": created_at,
                    "ttlAt": ttl_at,
                }
            )
            seq += 1
        elif text:
            events.append(
                {
                    "seq": seq,
                    "agentName": author,
                    "eventKind": "final_answer",
                    "toolName": None,
                    "toolArgs": None,
                    "toolResult": None,
                    "text": text,
                    "a2uiPayload": None,
                    "thoughtSignature": _encode_signature(thought_signature),
                    "createdAt": created_at,
                    "ttlAt": ttl_at,
                }
            )
            seq += 1

    return events


def extract_search_candidates(event_payload: dict) -> list[dict[str, Any]]:
    if event_payload.get("eventKind") != "tool_result":
        return []
    if event_payload.get("toolName") != "search_closet":
        return []
    result = event_payload.get("toolResult") or {}
    candidates = result.get("result") if isinstance(result, dict) else result
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def extract_style_result(event_payload: dict) -> dict | None:
    if event_payload.get("eventKind") != "tool_result":
        return None
    if event_payload.get("toolName") != "style_synthesizer":
        return None
    result = event_payload.get("toolResult") or {}
    image_url = result.get("coordinate_image_url") or result.get("coordinateImageUrl")
    if not image_url:
        return None
    return {
        "coordinateImageUrl": image_url,
        "items": result.get("items", []),
        "modelUsed": result.get("model_used") or result.get("modelUsed"),
    }
