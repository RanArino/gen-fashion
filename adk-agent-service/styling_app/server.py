import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from .agent import root_agent
from .adapters.firestore_session import FirestoreSessionRepository
from .config import get_settings
from .events import extract_style_result, normalize_adk_event
from .tools.search_closet import search_closet
from .tools.style_synthesizer import style_synthesizer


APP_NAME = "styling_app"
ADK_RUN_TIMEOUT_SECONDS = 45

app = FastAPI(title="gen-fashion ADK Agent Service", version="0.1.0")


class RunSessionRequest(BaseModel):
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(alias="userId")
    source: str
    user_preference: dict[str, Any] = Field(alias="userPreference")
    shared_closet_id: str | None = Field(default=None, alias="sharedClosetId")


@app.get("/health")
async def health():
    return {"status": "ok"}


async def require_internal_secret(x_internal_secret: str | None = Header(default=None)) -> None:
    configured = get_settings().internal_task_secret
    if not configured:
        raise HTTPException(status_code=503, detail="Internal endpoint is not configured")
    if not x_internal_secret or not secrets.compare_digest(x_internal_secret, configured):
        raise HTTPException(status_code=403, detail="Invalid or missing internal secret")


@app.post("/internal/run-session", status_code=202, dependencies=[Depends(require_internal_secret)])
async def run_session(request: RunSessionRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(execute_run_session, request)
    return {"accepted": True, "sessionId": request.session_id}


async def execute_run_session(
    request: RunSessionRequest,
    *,
    session_repo: FirestoreSessionRepository | None = None,
    runner: Runner | None = None,
) -> None:
    session_repo = session_repo or FirestoreSessionRepository()
    session_service = InMemorySessionService()
    runner = runner or Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    state = {
        "sessionId": request.session_id,
        "userId": request.user_id,
        "source": request.source,
        "sharedClosetId": request.shared_closet_id,
        "userPreference": request.user_preference,
    }

    seq = 1
    current_status: str | None = None

    async def set_status(status: str) -> None:
        nonlocal current_status
        if current_status == status:
            return
        await session_repo.update_status(request.session_id, status)
        current_status = status

    try:
        await set_status("SEARCHING")
        created_at = datetime.now(timezone.utc)
        await session_repo.write_event(
            request.session_id,
            {
                "seq": seq,
                "agentName": APP_NAME,
                "eventKind": "thinking",
                "toolName": None,
                "toolArgs": None,
                "toolResult": None,
                "text": "Styling session accepted",
                "a2uiPayload": None,
                "thoughtSignature": None,
                "createdAt": created_at,
                "ttlAt": created_at + timedelta(hours=24),
            },
        )
        seq += 1

        created = session_service.create_session(
            app_name=APP_NAME,
            user_id=request.user_id,
            session_id=request.session_id,
            state=state,
        )
        if hasattr(created, "__await__"):
            await created

        message = types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        "Create a complete outfit coordination for this session. "
                        f"Use source={request.source}, sharedClosetId={request.shared_closet_id}, "
                        f"preference={request.user_preference}."
                    )
                )
            ],
        )

        final_style_result = None
        try:
            async with asyncio.timeout(ADK_RUN_TIMEOUT_SECONDS):
                async for event in runner.run_async(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    new_message=message,
                    state_delta=state,
                ):
                    for normalized in normalize_adk_event(event, seq):
                        await session_repo.write_event(request.session_id, normalized)
                        seq = int(normalized["seq"]) + 1
                        if (
                            normalized.get("toolName") == "style_synthesizer"
                            and current_status != "GENERATING"
                        ):
                            await set_status("PROPOSING")
                            await set_status("GENERATING")
                        maybe_result = extract_style_result(normalized)
                        if maybe_result is not None:
                            final_style_result = maybe_result
        except TimeoutError:
            await session_repo.write_event(
                request.session_id,
                _event(
                    seq,
                    agent_name=APP_NAME,
                    event_kind="thinking",
                    text="ADK run timed out; continuing with deterministic fallback",
                ),
            )
            seq += 1

        if final_style_result is not None:
            await session_repo.write_style_result(request.session_id, final_style_result)
        else:
            fallback_result = await _run_deterministic_fallback(request, session_repo, seq)
            if fallback_result is not None:
                await session_repo.write_style_result(request.session_id, fallback_result)
            else:
                await session_repo.mark_error(
                    request.session_id,
                    "ADK run finished without a coordinate image URL",
                )
    except Exception as exc:
        await session_repo.mark_error(request.session_id, str(exc))
        raise


async def _run_deterministic_fallback(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    seq: int,
) -> dict[str, Any] | None:
    preference = request.user_preference
    colors = _preference_colors(preference)
    style_text = _style_description(preference)
    selected: list[dict[str, Any]] = []

    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name=APP_NAME,
            event_kind="thinking",
            text="Running deterministic coordination fallback",
        ),
    )
    seq += 1

    for category, description in (
        ("top", f"{style_text} top"),
        ("bottom", f"{style_text} pants or skirt"),
    ):
        tool_args = {
            "description": description,
            "source": request.source,
            "user_id": request.user_id,
            "shared_closet_id": request.shared_closet_id,
            "category": category,
            "colors": colors,
        }
        await session_repo.write_event(
            request.session_id,
            _event(
                seq,
                agent_name="ClosetAgent",
                event_kind="tool_call",
                tool_name="search_closet",
                tool_args=tool_args,
            ),
        )
        seq += 1
        candidates = search_closet(**tool_args)
        await session_repo.write_event(
            request.session_id,
            _event(
                seq,
                agent_name="ClosetAgent",
                event_kind="tool_result",
                tool_name="search_closet",
                tool_result={"result": candidates},
            ),
        )
        seq += 1
        if candidates:
            selected.append(candidates[0])

    image_urls = [item["image_url"] for item in selected if item.get("image_url")]
    if not image_urls:
        return None

    await session_repo.update_status(request.session_id, "PROPOSING")
    await session_repo.update_status(request.session_id, "GENERATING")
    synth_args = {
        "user_id": request.user_id,
        "item_image_urls": image_urls,
        "style_description": style_text,
    }
    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name="StylingAgent",
            event_kind="tool_call",
            tool_name="style_synthesizer",
            tool_args=synth_args,
        ),
    )
    seq += 1
    result = style_synthesizer(**synth_args)
    result["selected_items"] = selected
    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name="StylingAgent",
            event_kind="tool_result",
            tool_name="style_synthesizer",
            tool_result=result,
        ),
    )
    seq += 1
    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name="StylingAgent",
            event_kind="final_answer",
            text="Coordinate image generated.",
        ),
    )
    return {
        "coordinateImageUrl": result["coordinate_image_url"],
        "items": result.get("items", []),
        "modelUsed": result.get("model_used"),
        "selectedItems": selected,
    }


def _event(
    seq: int,
    *,
    agent_name: str,
    event_kind: str,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    tool_result: dict[str, Any] | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    created_at = datetime.now(timezone.utc)
    return {
        "seq": seq,
        "agentName": agent_name,
        "eventKind": event_kind,
        "toolName": tool_name,
        "toolArgs": tool_args,
        "toolResult": tool_result,
        "text": text,
        "a2uiPayload": None,
        "thoughtSignature": None,
        "createdAt": created_at,
        "ttlAt": created_at + timedelta(hours=24),
    }


def _preference_colors(preference: dict[str, Any]) -> list[str] | None:
    raw = preference.get("colorPreference") or preference.get("color_preference")
    if not raw:
        return None
    colors = [
        token.strip().lower()
        for part in str(raw).replace("/", ",").replace(" and ", ",").split(",")
        for token in [part]
        if token.strip()
    ]
    return colors or None


def _style_description(preference: dict[str, Any]) -> str:
    parts = [
        preference.get("occasion"),
        preference.get("season"),
        preference.get("style"),
        preference.get("colorPreference") or preference.get("color_preference"),
    ]
    return " ".join(str(part) for part in parts if part) or "clean casual outfit"
