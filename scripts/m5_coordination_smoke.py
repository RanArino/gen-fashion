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
                    if event_name in {"session.completed", "session.error"}:
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
    parser.add_argument("--project", default="animation-agent")
    parser.add_argument("--shared-closet-id", default="adult-01")
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
            },
        },
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    if selected["status"] != "SEARCHING":
        raise RuntimeError(f"Unexpected select-source response: {selected}")

    events = stream_events(args, token, session_id)
    terminal = events[-1]
    document = firestore_session(args, session_id)
    status = field_string(document, "status")
    event_kinds = [
        event["data"].get("eventKind")
        for event in events
        if event["event"] == "agent.event"
    ]

    if terminal["event"] != "session.completed" or status != "COMPLETED":
        raise RuntimeError(
            "M5 session did not complete: "
            f"terminal={terminal}, status={status}, event_kinds={event_kinds}"
        )

    print(
        json.dumps(
            {
                "session_id": session_id,
                "user_id": user_id,
                "status": status,
                "event_count": len(events),
                "event_kinds": event_kinds,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
