import asyncio
import json
import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import verify_firebase_token
from app.dependencies import (
    get_create_session_use_case,
    get_select_candidates_use_case,
    get_select_source_use_case,
    get_styling_repository,
)
from app.domain.styling import (
    ClothingSource,
    StyleSession,
    StyleSessionId,
    StyleSessionNotFound,
    UserPreference,
)
from app.domain.styling.exceptions import DailyGenerationLimitExceeded
from app.ports import StylingRepositoryPort
from app.use_cases.styling import (
    AgentRunStartFailed,
    CreateSessionUseCase,
    SelectCandidatesUseCase,
    SelectClothingSourceUseCase,
)


router = APIRouter()
STREAM_POLL_SECONDS = 1
# Must exceed the ADK run timeout (adk-agent-service adk_run_timeout_seconds, 90s)
# plus the deterministic-fallback time, so the client sees COMPLETED instead of a
# premature stream TIMEOUT when the primary agent path runs long.
STREAM_MAX_SECONDS = 150


class UserPreferenceRequest(BaseModel):
    occasion: str | None = None
    season: str | None = None
    style: str | None = None
    color_preference: str | None = Field(default=None, alias="colorPreference")
    gender: str | None = None

    def to_domain(self) -> UserPreference:
        return UserPreference(
            occasion=self.occasion,
            season=self.season,
            style=self.style,
            color_preference=self.color_preference,
            gender=self.gender,
        )


class SelectSourceRequest(BaseModel):
    source: ClothingSource
    user_preference: UserPreferenceRequest = Field(alias="userPreference")
    shared_closet_id: str | None = Field(default=None, alias="sharedClosetId")


class SelectCandidatesRequest(BaseModel):
    selected_item_ids: list[str] = Field(alias="selectedItemIds")


class SelectedItemResponse(BaseModel):
    item_id: str
    image_url: str
    category: str | None = None
    gender: str | None = None


class StyleResultResponse(BaseModel):
    coordinate_image_url: str


class SessionHistoryItem(BaseModel):
    session_id: str
    status: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    source: str | None = None
    shared_closet_id: str | None = None
    selected_items: list[SelectedItemResponse] = Field(default_factory=list)
    proposed_candidates: list[dict] = Field(default_factory=list)
    style_result: StyleResultResponse | None = None


def _session_to_history_item(session: StyleSession) -> SessionHistoryItem:
    return SessionHistoryItem(
        session_id=str(session.id),
        status=session.state.value,
        created_at=session.created_at,
        completed_at=session.completed_at,
        source=session.clothing_source.value,
        shared_closet_id=session.shared_closet_id,
        selected_items=[
            SelectedItemResponse(
                item_id=item.get("item_id", ""),
                image_url=item.get("image_url", ""),
                category=item.get("category"),
                gender=item.get("gender"),
            )
            for item in session.selected_items
        ],
        proposed_candidates=session.proposed_candidates,
        style_result=(
            StyleResultResponse(
                coordinate_image_url=session.final_result.coordinate_image_url
            )
            if session.final_result is not None
            else None
        ),
    )


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.get("", response_model=list[SessionHistoryItem])
async def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(verify_firebase_token),
    styling_repo: StylingRepositoryPort = Depends(get_styling_repository),
):
    sessions = await styling_repo.list_completed(user_id, limit=limit)
    return [_session_to_history_item(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionHistoryItem)
async def get_session(
    session_id: str,
    user_id: str = Depends(verify_firebase_token),
    styling_repo: StylingRepositoryPort = Depends(get_styling_repository),
):
    try:
        style_session_id = StyleSessionId(UUID(session_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session id") from exc
    session = await styling_repo.get_by_id(user_id, style_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Style session not found")
    return _session_to_history_item(session)


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


@router.post("/{session_id}/select", status_code=202)
async def select_candidates(
    session_id: str,
    request: SelectCandidatesRequest,
    user_id: str = Depends(verify_firebase_token),
    use_case: SelectCandidatesUseCase = Depends(get_select_candidates_use_case),
):
    try:
        result = await use_case.execute(user_id, session_id, request.selected_item_ids)
    except StyleSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "Cannot select candidates" in message else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
    except DailyGenerationLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AgentRunStartFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
    except DailyGenerationLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
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
            if refreshed.state.value == "PROPOSING" and not refreshed.selected_items:
                async for event_payload in drain_events():
                    yield event_payload
                yield _sse(
                    "session.proposed",
                    {
                        "sessionId": session_id,
                        "status": "PROPOSING",
                        "candidates": refreshed.proposed_candidates,
                    },
                )
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
