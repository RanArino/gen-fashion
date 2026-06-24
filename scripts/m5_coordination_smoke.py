#!/usr/bin/env python3
import argparse
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def request_json(method, url, *, body=None, headers=None, expected=(200,), timeout=60):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            if response.status not in expected:
                raise RuntimeError(f"{method} {url} returned {response.status}: {payload}")
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        if exc.code in expected:
            return json.loads(payload) if payload else {}
        raise RuntimeError(f"{method} {url} returned {exc.code}: {payload}") from exc


def auth_token(args):
    email = f"m5-e2e-{uuid4().hex[:12]}@example.com"
    response = request_json(
        "POST",
        f"{args.auth_emulator}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        body={
            "email": email,
            "password": "Password123!",
            "returnSecureToken": True,
        },
        headers={"Content-Type": "application/json"},
    )
    return response["idToken"], response["localId"]


def stream_events(args, token, session_id):
    request = Request(
        f"{args.api}/sessions/{session_id}/stream",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    deadline = time.time() + args.timeout_seconds
    events = []
    event_name = None
    data_lines = []
    with urlopen(request, timeout=args.timeout_seconds + 5) as response:
        if response.status != 200:
            payload = response.read().decode("utf-8")
            raise RuntimeError(f"SSE returned {response.status}: {payload}")
        while time.time() < deadline:
            line = response.readline().decode("utf-8")
            if line == "":
                break
            line = line.rstrip("\r\n")
            if not line:
                if event_name and data_lines:
                    payload = json.loads("\n".join(data_lines))
                    events.append({"event": event_name, "data": payload})
                    if event_name in {
                        "session.proposed",
                        "session.completed",
                        "session.error",
                    }:
                        return events
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
    raise RuntimeError(f"Timed out waiting for terminal SSE event; saw {len(events)} events")


def firestore_session(args, session_id):
    url = (
        f"{args.firestore_emulator}/v1/projects/{args.project}/databases/(default)"
        f"/documents/sessions/{session_id}"
    )
    return request_json("GET", url)


def field_string(document, name):
    return document.get("fields", {}).get(name, {}).get("stringValue")


def main():
    parser = argparse.ArgumentParser(description="Run the M5 coordination backend smoke test.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--auth-emulator", default="http://localhost:9099")
    parser.add_argument("--firestore-emulator", default="http://localhost:8080")
    parser.add_argument("--project", default="gen-fashion-local")
    parser.add_argument("--shared-closet-id", default="adult-01")
    parser.add_argument("--gender", choices=("male", "female", "common"), default="common")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    token, user_id = auth_token(args)
    auth_header = {"Authorization": f"Bearer {token}"}

    created = request_json("POST", f"{args.api}/sessions", headers=auth_header)
    session_id = created["session_id"]
    if created["status"] != "SOURCE_SELECTING":
        raise RuntimeError(f"Unexpected create response: {created}")

    selected = request_json(
        "POST",
        f"{args.api}/sessions/{session_id}/source",
        body={
            "source": "SHARED_CLOSET",
            "sharedClosetId": args.shared_closet_id,
            "userPreference": {
                "occasion": "casual weekend",
                "season": "spring",
                "style": "clean casual",
                "colorPreference": "blue and white",
                "gender": args.gender,
            },
        },
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    if selected["status"] != "SEARCHING":
        raise RuntimeError(f"Unexpected select-source response: {selected}")

    propose_events = stream_events(args, token, session_id)
    proposed = propose_events[-1]
    if proposed["event"] != "session.proposed":
        raise RuntimeError(f"Session did not pause for selection: {proposed}")
    candidates = proposed["data"].get("candidates", [])
    if not candidates:
        raise RuntimeError("Propose phase returned no candidates")

    propose_agent_events = [
        event["data"]
        for event in propose_events
        if event["event"] == "agent.event"
    ]
    if any(event.get("toolName") == "style_synthesizer" for event in propose_agent_events):
        raise RuntimeError("Propose phase exposed style_synthesizer")
    if not any(
        event.get("toolName") == "transfer_to_agent"
        for event in propose_agent_events
    ):
        raise RuntimeError("Propose phase has no LLM delegation event")
    search_calls = [
        event
        for event in propose_agent_events
        if event.get("eventKind") == "tool_call"
        and event.get("toolName") == "search_closet"
    ]
    if not search_calls:
        raise RuntimeError("Propose phase has no agent search call")
    if any(
        event.get("text") == "Agent returned no candidates; running search fallback"
        for event in propose_agent_events
    ):
        raise RuntimeError("Propose phase used deterministic search fallback")
    search_descriptions = [
        (event.get("toolArgs") or {}).get("description") for event in search_calls
    ]
    if any(not description for description in search_descriptions):
        raise RuntimeError(f"Agent search description missing: {search_descriptions}")
    if any(
        (event.get("toolArgs") or {}).get("gender") != args.gender
        for event in search_calls
    ):
        raise RuntimeError("Gender was not propagated to every agent search")

    before_selection = firestore_session(args, session_id)
    style_result = before_selection.get("fields", {}).get("styleResult", {})
    if style_result and "nullValue" not in style_result:
        raise RuntimeError("Coordinate was generated before explicit selection")

    selected_candidates = candidates[:2]
    candidate_ids = [
        candidate.get("item_id") or candidate.get("itemId")
        for candidate in selected_candidates
    ]
    selected_image_urls = [
        candidate.get("image_url") or candidate.get("imageUrl")
        for candidate in selected_candidates
    ]
    if any(not url for url in selected_image_urls):
        raise RuntimeError(f"Selected candidate is missing an image URL: {selected_candidates}")
    request_json(
        "POST",
        f"{args.api}/sessions/{session_id}/select",
        body={"selectedItemIds": candidate_ids},
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )

    generate_events = stream_events(args, token, session_id)
    events = propose_events + generate_events
    terminal = generate_events[-1]
    document = firestore_session(args, session_id)
    status = field_string(document, "status")
    event_kinds = [
        event["data"].get("eventKind")
        for event in events
        if event["event"] == "agent.event"
    ]
    generate_agent_events = [
        event["data"]
        for event in generate_events
        if event["event"] == "agent.event"
    ]
    synth_calls = [
        event
        for event in generate_agent_events
        if event.get("eventKind") == "tool_call"
        and event.get("toolName") == "style_synthesizer"
    ]
    if not synth_calls:
        raise RuntimeError("Generate phase has no StylingAgent synthesizer call")
    synth_args = synth_calls[-1].get("toolArgs") or {}
    expected_wearer_age = "child" if args.shared_closet_id.startswith("child-") else "adult"
    if synth_args.get("gender") != args.gender:
        raise RuntimeError(f"Generate gender mismatch: {synth_args}")
    if synth_args.get("wearer_age") != expected_wearer_age:
        raise RuntimeError(f"Generate wearer_age mismatch: {synth_args}")
    if synth_args.get("user_id") != user_id:
        raise RuntimeError(f"Generate user_id mismatch: {synth_args}")
    synth_image_urls = synth_args.get("item_image_urls") or []
    if synth_image_urls != selected_image_urls:
        raise RuntimeError(
            "Generate synthesizer image URLs do not match the selected candidates: "
            f"synth={synth_image_urls} selected={selected_image_urls}"
        )

    if terminal["event"] != "session.completed" or status != "COMPLETED":
        raise RuntimeError(
            "M5 session did not complete: "
            f"terminal={terminal}, status={status}, event_kinds={event_kinds}"
        )

    history = request_json(
        "GET",
        f"{args.api}/sessions?limit=20",
        headers=auth_header,
    )
    history_item = next(
        (item for item in history if item.get("session_id") == session_id),
        None,
    )
    if history_item is None:
        raise RuntimeError("Completed session is missing from GET /sessions")
    if not history_item.get("completed_at"):
        raise RuntimeError(f"History item is missing completed_at: {history_item}")
    coordinate_image_url = (history_item.get("style_result") or {}).get(
        "coordinate_image_url"
    )
    if not coordinate_image_url:
        raise RuntimeError(f"History item is missing coordinate image: {history_item}")

    print(
        json.dumps(
            {
                "session_id": session_id,
                "user_id": user_id,
                "status": status,
                "event_count": len(events),
                "event_kinds": event_kinds,
                "search_descriptions": search_descriptions,
                "synth_args": synth_args,
                "selected_image_urls": selected_image_urls,
                "history_completed_at": history_item["completed_at"],
                "history_coordinate_image_url": coordinate_image_url,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
