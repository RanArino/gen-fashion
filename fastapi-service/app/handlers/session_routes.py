import asyncio
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import verify_firebase_token
from app.dependencies import get_create_session_use_case, get_select_source_use_case, get_styling_repository
from app.domain.styling import ClothingSource, StyleSessionId, StyleSessionNotFound, UserPreference
from app.use_cases.styling import AgentRunStartFailed, CreateSessionUseCase, SelectClothingSourceUseCase


router = APIRouter()
STREAM_POLL_SECONDS = 1
STREAM_MAX_SECONDS = 120


class UserPreferenceRequest(BaseModel):
    occasion: str | None = None
    season: str | None = None
    style: str | None = None
    color_preference: str | None = Field(default=None, alias="colorPreference")

    def to_domain(self) -> UserPreference:
        return UserPreference(
            occasion=self.occasion,
            season=self.season,
            style=self.style,
            color_preference=self.color_preference,
        )


class SelectSourceRequest(BaseModel):
    source: ClothingSource
    user_preference: UserPreferenceRequest = Field(alias="userPreference")
    shared_closet_id: str | None = Field(default=None, alias="sharedClosetId")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("")
async def create_session(
    user_id: str = Depends(verify_firebase_token),
    use_case: CreateSessionUseCase = Depends(get_create_session_use_case),
):
    """Create a style session (M5-1)."""
    result = await use_case.execute(user_id)
    return {
        "session_id": result.session_id,
        "status": result.status,
        "source": result.source,
    }


@router.post("/{session_id}/source", status_code=202)
async def select_source(
    session_id: str,
    request: SelectSourceRequest,
    user_id: str = Depends(verify_firebase_token),
    use_case: SelectClothingSourceUseCase = Depends(get_select_source_use_case),
):
    """Select clothing source (M5-3)."""
    try:
        result = await use_case.execute(
            user_id=user_id,
            session_id=session_id,
            source=request.source,
            preference=request.user_preference.to_domain(),
            shared_closet_id=request.shared_closet_id,
        )
    except StyleSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "Cannot select source" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except AgentRunStartFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "session_id": result.session_id,
        "status": result.status,
        "source": result.source,
    }


@router.get("/{session_id}/stream")
async def stream_session_events(
    session_id: str,
    user_id: str = Depends(verify_firebase_token),
    styling_repo=Depends(get_styling_repository),
):
    """Stream agent events via SSE (M5-9)."""
    style_session_id = StyleSessionId(UUID(session_id))
    session = await styling_repo.get_by_id(user_id, style_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Style session not found")

    async def event_generator():
        last_seq = 0
        last_keepalive = 0
        started_at = time.monotonic()

        async def drain_events():
            nonlocal last_seq
            for event in await styling_repo.list_events(
                user_id, style_session_id, after_seq=last_seq
            ):
                seq = int(event.get("seq", 0))
                last_seq = max(last_seq, seq)
                yield _sse("agent.event", {"sessionId": session_id, **event})

        yield _sse(
            "session.snapshot",
            {
                "sessionId": session_id,
                "status": session.state.value,
                "source": session.clothing_source.value,
            },
        )
        while True:
            async for event_payload in drain_events():
                yield event_payload

            refreshed = await styling_repo.get_by_id(user_id, style_session_id)
            if refreshed is None:
                yield _sse("session.error", {"sessionId": session_id, "status": "ERROR"})
                return
            if refreshed.state.value in {"COMPLETED", "ERROR", "TIMEOUT"}:
                async for event_payload in drain_events():
                    yield event_payload
                event_name = (
                    "session.completed"
                    if refreshed.state.value == "COMPLETED"
                    else "session.error"
                )
                yield _sse(event_name, {"sessionId": session_id, "status": refreshed.state.value})
                return
            if time.monotonic() - started_at >= STREAM_MAX_SECONDS:
                yield _sse("session.error", {"sessionId": session_id, "status": "TIMEOUT"})
                return
            if last_keepalive >= 15:
                yield ": keepalive\n\n"
                last_keepalive = 0
            await asyncio.sleep(STREAM_POLL_SECONDS)
            last_keepalive += 1

    return StreamingResponse(event_generator(), media_type="text/event-stream")
