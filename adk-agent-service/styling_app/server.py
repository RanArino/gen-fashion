import asyncio
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from .agent import build_agent_for_phase
from .adapters.firestore_session import FirestoreSessionRepository
from .config import get_settings
from .events import (
    extract_search_candidates,
    extract_style_result,
    normalize_adk_event,
)
from .adapters.rakuten import RakutenUnavailableError
from .tools.search_closet import search_closet
from .tools.search_rakuten import search_rakuten
from .tools.style_synthesizer import style_synthesizer


APP_NAME = "styling_app"
logger = logging.getLogger(__name__)

app = FastAPI(title="gen-fashion ADK Agent Service", version="0.1.0")


class RunSessionRequest(BaseModel):
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(alias="userId")
    source: str
    user_preference: dict[str, Any] = Field(alias="userPreference")
    shared_closet_id: str | None = Field(default=None, alias="sharedClosetId")
    phase: str = "propose"
    selected_items: list[dict[str, Any]] | None = Field(default=None, alias="selectedItems")
    mode: str = "standard"
    anchor_items: list[dict[str, Any]] | None = Field(default=None, alias="anchorItems")

    @property
    def assisted(self) -> bool:
        return self.mode == "assisted"


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
    try:
        seq = await session_repo.next_seq(request.session_id)
        closet_kind = await _resolve_closet_kind(request, session_repo)
        gender = request.user_preference.get("gender") or "common"
        language = _language_code(request.user_preference)

        if request.phase == "propose":
            await session_repo.update_status(request.session_id, "SEARCHING")
            if request.assisted:
                message = (
                    "Propose a complete styling around the user's anchor items. "
                    "Treat anchorItems as fixed context, delegate to ClosetAgent, "
                    "let it describe each complementary garment or accessory "
                    "(e.g. white t-shirt, black hat, bag, shoes, belt). Build "
                    "only one coordinate, so balance suggestions across missing "
                    "outfit slots and do not auto-recommend multiple items for "
                    "the same category. Call search_rakuten with a concrete "
                    "query and category hint per suggestion, then "
                    "stop after returning candidates. Context: "
                    f"{_message_context(request, gender, closet_kind, language)}"
                )
            else:
                message = (
                    "Propose outfit candidates only. Delegate closet searches to "
                    "ClosetAgent, let it create concrete descriptions for each "
                    "garment type, and stop after returning candidates. Context: "
                    f"{_message_context(request, gender, closet_kind, language)}"
                )
            normalized_events, seq = await _run_adk_phase(
                request,
                session_repo,
                runner=runner,
                seq=seq,
                wearer_age=closet_kind,
                message=message,
            )
            candidates = _collect_candidates(normalized_events)
            if request.assisted:
                candidates, seq = await _finalize_assisted_candidates(
                    request, session_repo, seq, candidates
                )
            elif not candidates:
                await session_repo.write_event(
                    request.session_id,
                    _event(
                        seq,
                        agent_name=APP_NAME,
                        event_kind="thinking",
                        text="Agent returned no candidates; running search fallback",
                    ),
                )
                candidates = await _run_search_fallback(
                    request, session_repo, seq + 1, gender
                )
            if not candidates:
                await session_repo.mark_error(request.session_id, "No clothing candidates found")
                return
            await session_repo.write_proposed_candidates(request.session_id, candidates)
            return

        if request.phase == "generate":
            if not request.selected_items:
                await session_repo.mark_error(request.session_id, "Candidate selection is required")
                return
            selected_image_urls = _selected_image_urls(request.selected_items)
            if len(selected_image_urls) != len(request.selected_items):
                await session_repo.mark_error(
                    request.session_id, "Selected items have no images"
                )
                return
            await session_repo.update_status(request.session_id, "GENERATING")
            normalized_events, seq = await _run_adk_phase(
                request,
                session_repo,
                runner=runner,
                seq=seq,
                wearer_age=closet_kind,
                message=(
                    "Generate one coordinate image for the already-selected "
                    "garments. Call style_synthesizer; you may only set an "
                    "optional style_description. Context: "
                    f"{_message_context(request, gender, closet_kind, language)}"
                ),
            )
            result = _collect_style_result(
                normalized_events, request.selected_items, selected_image_urls
            )
            if result is None:
                await session_repo.write_event(
                    request.session_id,
                    _event(
                        seq,
                        agent_name=APP_NAME,
                        event_kind="thinking",
                        text="Agent returned no image; running consented generation fallback",
                    ),
                )
                result = await _run_generate_fallback(
                    request,
                    session_repo,
                    seq + 1,
                    gender=gender,
                    wearer_age=closet_kind,
                    language=language,
                )
            if result is None:
                await session_repo.mark_error(request.session_id, "Selected items have no images")
                return
            await session_repo.write_style_result(request.session_id, result)
            return

        raise ValueError(f"Unsupported run phase: {request.phase}")
    except Exception as exc:
        await session_repo.mark_error(request.session_id, str(exc))
        raise


async def _run_adk_phase(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    *,
    runner: Runner | None,
    seq: int,
    wearer_age: str,
    message: str,
) -> tuple[list[dict[str, Any]], int]:
    session_service = InMemorySessionService()
    gender = request.user_preference.get("gender") or "common"
    language = _language_code(request.user_preference)
    search_tool = None
    style_tool = None
    rakuten_tool = None
    selected_image_urls: list[str] = []
    selected_item_categories: list[str | None] = []
    if request.phase == "propose":
        search_tool = _build_propose_search_tool(request, gender)
        if request.assisted:
            rakuten_tool = _build_propose_rakuten_tool()
    elif request.phase == "generate":
        selected_image_urls = _selected_image_urls(request.selected_items)
        selected_item_categories = _selected_item_categories(request.selected_items)
        style_tool = _build_generate_style_tool(request, gender, wearer_age, language)
    active_runner = runner or Runner(
        agent=build_agent_for_phase(
            request.phase,
            search_tool=search_tool,
            style_tool=style_tool,
            rakuten_tool=rakuten_tool,
            assisted=request.assisted,
        ),
        app_name=APP_NAME,
        session_service=session_service,
    )
    state = {
        "sessionId": request.session_id,
        "userId": request.user_id,
        "source": request.source,
        "sharedClosetId": request.shared_closet_id,
        "userPreference": request.user_preference,
        "phase": request.phase,
        "mode": request.mode,
        "anchorItems": request.anchor_items or [],
        "selectedItems": request.selected_items or [],
        "gender": request.user_preference.get("gender") or "common",
        "wearerAge": wearer_age,
        "language": language,
    }
    created = session_service.create_session(
        app_name=APP_NAME,
        user_id=request.user_id,
        session_id=request.session_id,
        state=state,
    )
    if hasattr(created, "__await__"):
        await created

    normalized_events: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(get_settings().adk_run_timeout_seconds):
            async for event in active_runner.run_async(
                user_id=request.user_id,
                session_id=request.session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=message)],
                ),
                state_delta=state,
            ):
                for normalized in normalize_adk_event(event, seq):
                    if (
                        request.phase == "propose"
                        and normalized.get("eventKind") == "tool_call"
                        and normalized.get("toolName") == "search_closet"
                    ):
                        normalized["toolArgs"] = {
                            **(normalized.get("toolArgs") or {}),
                            "source": request.source,
                            "user_id": request.user_id,
                            "shared_closet_id": request.shared_closet_id,
                            "gender": gender,
                        }
                    elif (
                        request.phase == "generate"
                        and normalized.get("eventKind") == "tool_call"
                        and normalized.get("toolName") == "style_synthesizer"
                    ):
                        llm_style = (normalized.get("toolArgs") or {}).get(
                            "style_description"
                        )
                        normalized["toolArgs"] = {
                            "user_id": request.user_id,
                            "item_image_urls": selected_image_urls,
                            "style_description": _effective_style_description(
                                llm_style, request.user_preference
                            ),
                            "gender": gender,
                            "wearer_age": wearer_age,
                            "language": language,
                            "item_categories": selected_item_categories,
                        }
                    await session_repo.write_event(request.session_id, normalized)
                    normalized_events.append(normalized)
                    seq = int(normalized["seq"]) + 1
    except TimeoutError:
        await session_repo.write_event(
            request.session_id,
            _event(
                seq,
                agent_name=APP_NAME,
                event_kind="thinking",
                text=f"ADK {request.phase} run timed out",
            ),
        )
        seq += 1
    return normalized_events, seq


def _build_propose_search_tool(
    request: RunSessionRequest,
    gender: str,
):
    bound_gender = gender

    def phase_search_closet(
        description: str,
        source: str | None = None,
        user_id: str | None = None,
        shared_closet_id: str | None = None,
        category: str | None = None,
        colors: list[str] | None = None,
        gender: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        return search_closet(
            description=description,
            source=request.source,
            user_id=request.user_id,
            shared_closet_id=request.shared_closet_id,
            category=category,
            colors=colors,
            gender=bound_gender,
            limit=limit,
        )

    phase_search_closet.__name__ = "search_closet"
    phase_search_closet.__doc__ = search_closet.__doc__
    return phase_search_closet


def _build_propose_rakuten_tool():
    def phase_search_rakuten(
        query: str,
        category: str | None = None,
        colors: list[str] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        # A raised tool error aborts the whole ADK run; Rakuten being down or
        # unconfigured must instead degrade to closet/anchor-only proposals.
        try:
            return search_rakuten(
                query=query, category=category, colors=colors, limit=limit
            )
        except RakutenUnavailableError as exc:
            logger.warning("search_rakuten unavailable: %s", exc)
            return []

    phase_search_rakuten.__name__ = "search_rakuten"
    phase_search_rakuten.__doc__ = search_rakuten.__doc__
    return phase_search_rakuten


MAX_DEFAULT_RECOMMENDED_SUGGESTIONS = 3


async def _finalize_assisted_candidates(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    seq: int,
    collected: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Merge fixed anchors with agent/fallback suggestions (MK-4/MK-5).

    Anchors always lead and are recommended; when the agent produced no
    Rakuten suggestion, one deterministic Rakuten query runs as fallback.
    Rakuten unavailability degrades to anchor/closet-only candidates instead
    of failing the session.
    """
    anchors = list(request.anchor_items or [])
    external = [item for item in collected if item.get("source") == "RAKUTEN"]
    if not external:
        await session_repo.write_event(
            request.session_id,
            _event(
                seq,
                agent_name=APP_NAME,
                event_kind="thinking",
                text="Agent returned no purchasable suggestions; running Rakuten fallback",
            ),
        )
        seq += 1
        collected, seq = await _run_assisted_rakuten_fallback(
            request, session_repo, seq, collected
        )

    candidates_by_id: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        item_id = str(anchor.get("item_id") or anchor.get("itemId") or "")
        if item_id:
            candidates_by_id[item_id] = {**anchor, "anchor": True, "recommended": True}
    recommended_left = MAX_DEFAULT_RECOMMENDED_SUGGESTIONS
    for candidate in collected:
        item_id = str(candidate.get("item_id") or candidate.get("itemId") or "")
        if not item_id or item_id in candidates_by_id:
            continue
        if candidate.get("source") == "RAKUTEN" and "recommended" not in candidate:
            candidate = {**candidate, "recommended": recommended_left > 0}
            recommended_left -= 1 if candidate["recommended"] else 0
        candidates_by_id[item_id] = candidate
    return list(candidates_by_id.values()), seq


async def _run_assisted_rakuten_fallback(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    seq: int,
    collected: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Deterministic Rakuten query from the user preference (MK-4 fallback)."""
    tool_args = {
        "query": _style_description(request.user_preference),
        "colors": _preference_colors(request.user_preference),
        "limit": 5,
    }
    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name="ClosetAgent",
            event_kind="tool_call",
            tool_name="search_rakuten",
            tool_args=tool_args,
        ),
    )
    seq += 1
    try:
        suggestions = search_rakuten(**tool_args)
    except RakutenUnavailableError as exc:
        await session_repo.write_event(
            request.session_id,
            _event(
                seq,
                agent_name="ClosetAgent",
                event_kind="thinking",
                text=f"Rakuten suggestions unavailable: {exc}",
            ),
        )
        return collected, seq + 1
    await session_repo.write_event(
        request.session_id,
        _event(
            seq,
            agent_name="ClosetAgent",
            event_kind="tool_result",
            tool_name="search_rakuten",
            tool_result={"result": suggestions},
        ),
    )
    return [*collected, *suggestions], seq + 1


def _selected_image_urls(selected_items: list[dict[str, Any]] | None) -> list[str]:
    return [item["image_url"] for item in selected_items or [] if item.get("image_url")]


def _selected_item_categories(selected_items: list[dict[str, Any]] | None) -> list[str | None]:
    return [
        item.get("category")
        for item in selected_items or []
        if item.get("image_url")
    ]


def _effective_style_description(
    requested_style: Any, preference: dict[str, Any]
) -> str:
    if isinstance(requested_style, str) and requested_style.strip():
        return requested_style.strip()
    return _style_description(preference)


def _build_generate_style_tool(
    request: RunSessionRequest,
    gender: str,
    wearer_age: str,
    language: str,
):
    user_id = request.user_id
    image_urls = _selected_image_urls(request.selected_items)
    item_categories = _selected_item_categories(request.selected_items)
    bound_gender = gender
    bound_wearer_age = wearer_age
    bound_language = language

    def style_synthesizer_tool(style_description: str = "") -> dict:
        return style_synthesizer(
            user_id=user_id,
            item_image_urls=image_urls,
            style_description=_effective_style_description(
                style_description, request.user_preference
            ),
            gender=bound_gender,
            wearer_age=bound_wearer_age,
            language=bound_language,
            item_categories=item_categories,
        )

    style_synthesizer_tool.__name__ = "style_synthesizer"
    style_synthesizer_tool.__doc__ = (
        "Generate a coordinate image for the already-selected garments. Provide "
        "only an optional style_description; the requesting user, garment images, "
        "wearer gender, wearer age, and language are fixed by the server."
    )
    return style_synthesizer_tool


def _message_context(
    request: RunSessionRequest,
    gender: str,
    wearer_age: str,
    language: str,
) -> str:
    language_display = "English" if language == "en" else "Japanese"
    return json.dumps(
        {
            "sessionId": request.session_id,
            "userId": request.user_id,
            "source": request.source,
            "sharedClosetId": request.shared_closet_id,
            "userPreference": request.user_preference,
            "mode": request.mode,
            "anchorItems": request.anchor_items or [],
            "selectedItems": request.selected_items or [],
            "selectedItemImageUrls": [
                item["image_url"]
                for item in request.selected_items or []
                if item.get("image_url")
            ],
            "gender": gender,
            "wearerAge": wearer_age,
            "language": language,
            "languageInstruction": (
                "Author all natural-language output "
                f"(reasoning, item descriptions, final answer) in {language_display}."
            ),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _collect_candidates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        for candidate in extract_search_candidates(event):
            item_id = candidate.get("item_id") or candidate.get("itemId")
            if item_id:
                candidates_by_id.setdefault(str(item_id), candidate)
    return list(candidates_by_id.values())


def _collect_style_result(
    events: list[dict[str, Any]],
    selected_items: list[dict[str, Any]] | None,
    selected_image_urls: list[str],
) -> dict[str, Any] | None:
    result = None
    for event in events:
        maybe_result = extract_style_result(event)
        if maybe_result is not None:
            result = maybe_result
    if result is not None:
        result["items"] = selected_image_urls
        result["selectedItems"] = selected_items or []
    return result


async def _resolve_closet_kind(
    request: RunSessionRequest, session_repo: FirestoreSessionRepository
) -> str:
    if request.source != "SHARED_CLOSET":
        return "adult"
    if request.shared_closet_id:
        kind = await session_repo.get_closet_kind(request.shared_closet_id)
        if kind:
            return kind
        if request.shared_closet_id.startswith("child-"):
            return "child"
    return "adult"


async def _run_search_fallback(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    seq: int,
    gender: str,
) -> list[dict[str, Any]]:
    preference = request.user_preference
    colors = _preference_colors(preference)
    style_text = _style_description(preference)
    candidates_by_id: dict[str, dict[str, Any]] = {}

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
            "gender": gender,
            "limit": 5,
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
        for candidate in candidates:
            candidates_by_id.setdefault(candidate["item_id"], candidate)
    return list(candidates_by_id.values())


async def _run_generate_fallback(
    request: RunSessionRequest,
    session_repo: FirestoreSessionRepository,
    seq: int,
    *,
    gender: str,
    wearer_age: str,
    language: str,
) -> dict[str, Any] | None:
    selected = request.selected_items or []
    image_urls = [item["image_url"] for item in selected if item.get("image_url")]
    if not image_urls:
        return None
    item_categories = _selected_item_categories(selected)

    style_text = _style_description(request.user_preference)
    synth_args = {
        "user_id": request.user_id,
        "item_image_urls": image_urls,
        "style_description": style_text,
        "gender": gender,
        "wearer_age": wearer_age,
        "language": language,
        "item_categories": item_categories,
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
            text=(
                "Coordinate image generated."
                if language == "en"
                else "コーディネート画像を生成しました。"
            ),
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


def _language_code(preference: dict[str, Any]) -> str:
    return "en" if preference.get("language") == "en" else "ja"


def _style_description(preference: dict[str, Any]) -> str:
    parts = [
        preference.get("occasion"),
        preference.get("season"),
        preference.get("style"),
        preference.get("colorPreference") or preference.get("color_preference"),
    ]
    return " ".join(str(part) for part in parts if part) or "clean casual outfit"
