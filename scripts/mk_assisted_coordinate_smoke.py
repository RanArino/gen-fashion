#!/usr/bin/env python3
"""MK Assisted Coordinate backend smoke test.

Flow (against the `make dev` stack):
1. Sign up an emulator user and upload one closet item until READY (anchor).
2. Start an Assisted session with the anchor and stream to `session.proposed`.
3. Verify the anchor is proposed as a recommended candidate.
4. If a RAKUTEN candidate is present (live credentials configured), import it
   as Interesting, flip it to Owned, and reuse it in a Standard CLOSET run.
   Without credentials the Rakuten steps are exercised on the anchor item
   (ownership transitions) and a warning is printed; pass --require-rakuten
   to fail instead.
5. Generate from the selected candidates and require COMPLETED plus history.

Manual live-Rakuten checklist (when RAKUTEN_APPLICATION_ID/ACCESS_KEY are set):
- suggestions render with name, price, image, and outbound link
- `search_rakuten` tool calls appear in the trace
- import creates an Interesting closet item with external metadata
- the closet item card for an Interesting Rakuten item shows a link/button
  back to the Rakuten Ichiba product page
"""

import argparse
import json
import time
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw


def build_sample_jpeg() -> bytes:
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    shirt = [
        (58, 36),
        (76, 24),
        (84, 24),
        (102, 36),
        (130, 52),
        (118, 76),
        (106, 68),
        (106, 134),
        (54, 134),
        (54, 68),
        (42, 76),
        (30, 52),
    ]
    draw.polygon(shirt, fill=(45, 105, 190), outline=(20, 60, 130))
    draw.rectangle((66, 31, 94, 47), fill="white")
    output = BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


SAMPLE_JPEG = build_sample_jpeg()


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


def request_bytes(method, url, *, body=None, headers=None, expected=(200,)):
    request = Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read()
            if response.status not in expected:
                raise RuntimeError(f"{method} {url} returned {response.status}: {payload!r}")
            return payload
    except HTTPError as exc:
        payload = exc.read()
        if exc.code in expected:
            return payload
        raise RuntimeError(f"{method} {url} returned {exc.code}: {payload!r}") from exc


def ensure_bucket(args):
    s3 = boto3.client(
        "s3",
        endpoint_url=args.storage_endpoint,
        aws_access_key_id=args.storage_access_key,
        aws_secret_access_key=args.storage_secret_key,
        region_name="auto",
    )
    try:
        s3.create_bucket(Bucket=args.bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise
    return s3


def auth_token(args):
    response = request_json(
        "POST",
        f"{args.auth_emulator}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        body={"returnSecureToken": True},
        headers={"Content-Type": "application/json"},
    )
    return response["idToken"], response["localId"]


def firestore_closet_document(args, user_id, item_id, expected=(200,)):
    path = f"users/{quote(user_id)}/closet/{quote(item_id)}"
    url = (
        f"{args.firestore_emulator}/v1/projects/{args.project}"
        f"/databases/(default)/documents/{path}"
    )
    return request_json("GET", url, expected=expected)


def firestore_string(document, field_name):
    return document.get("fields", {}).get(field_name, {}).get("stringValue")


def upload_ready_anchor(args, auth_header, user_id):
    item_id = str(uuid4())
    upload = request_json(
        "GET",
        f"{args.api}/closet/upload-url?item_id={item_id}",
        headers=auth_header,
    )
    request_bytes(
        "PUT",
        upload["upload_url"],
        body=SAMPLE_JPEG,
        headers={"Content-Type": "image/jpeg"},
        expected=(200,),
    )
    request_json(
        "POST",
        f"{args.api}/closet/items/{item_id}/complete",
        headers=auth_header,
    )
    deadline = time.time() + args.timeout_seconds
    while time.time() < deadline:
        document = firestore_closet_document(args, user_id, item_id)
        status = firestore_string(document, "status")
        if status == "READY":
            return item_id, document
        if status == "ERROR":
            raise RuntimeError(f"Anchor analysis failed: {document}")
        time.sleep(1)
    raise RuntimeError("Timed out waiting for the anchor item to become READY")


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


def candidate_id(candidate):
    return candidate.get("item_id") or candidate.get("itemId")


def update_ownership(args, auth_header, item_id, ownership):
    return request_json(
        "PATCH",
        f"{args.api}/closet/items/{item_id}",
        body={"ownershipStatus": ownership},
        headers={**auth_header, "Content-Type": "application/json"},
    )


def run_generation(args, token, auth_header, session_id, selected_ids):
    request_json(
        "POST",
        f"{args.api}/sessions/{session_id}/select",
        body={"selectedItemIds": selected_ids},
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    events = stream_events(args, token, session_id)
    terminal = events[-1]
    if terminal["event"] != "session.completed":
        raise RuntimeError(f"Session did not complete: {terminal}")
    return events


def main():
    parser = argparse.ArgumentParser(description="Run the MK assisted coordinate smoke test.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--auth-emulator", default="http://localhost:9099")
    parser.add_argument("--firestore-emulator", default="http://localhost:8080")
    parser.add_argument("--project", default="gen-fashion-local")
    parser.add_argument("--storage-endpoint", default="http://localhost:9000")
    parser.add_argument("--storage-access-key", default="minioadmin")
    parser.add_argument("--storage-secret-key", default="minioadmin")
    parser.add_argument("--bucket", default="gen-fashion-images")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument(
        "--require-rakuten",
        action="store_true",
        help="Fail when the proposal has no RAKUTEN candidate (live credentials).",
    )
    args = parser.parse_args()

    ensure_bucket(args)
    token, user_id = auth_token(args)
    auth_header = {"Authorization": f"Bearer {token}"}

    anchor_id, _ = upload_ready_anchor(args, auth_header, user_id)

    # Anchor-count validation must fail before any ADK run.
    created = request_json("POST", f"{args.api}/sessions", headers=auth_header)
    request_json(
        "POST",
        f"{args.api}/sessions/{created['session_id']}/assist",
        body={"anchorItemIds": [], "userPreference": {}},
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(400,),
    )

    assisted = request_json(
        "POST",
        f"{args.api}/sessions/{created['session_id']}/assist",
        body={
            "anchorItemIds": [anchor_id],
            "userPreference": {
                "occasion": "casual weekend",
                "season": "spring",
                "style": "clean casual",
                "colorPreference": "blue and white",
                "gender": "common",
            },
        },
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    if assisted["status"] != "SEARCHING" or assisted["source"] != "CLOSET":
        raise RuntimeError(f"Unexpected assist response: {assisted}")
    session_id = assisted["session_id"]

    propose_events = stream_events(args, token, session_id)
    proposed = propose_events[-1]
    if proposed["event"] != "session.proposed":
        raise RuntimeError(f"Assisted session did not pause for selection: {proposed}")
    candidates = proposed["data"].get("candidates", [])
    anchor_candidates = [c for c in candidates if candidate_id(c) == anchor_id]
    if not anchor_candidates or anchor_candidates[0].get("recommended") is not True:
        raise RuntimeError(f"Anchor is not a recommended candidate: {candidates}")
    rakuten_candidates = [c for c in candidates if c.get("source") == "RAKUTEN"]
    if args.require_rakuten and not rakuten_candidates:
        raise RuntimeError("No RAKUTEN candidates in the assisted proposal")

    imported_item_id = None
    if rakuten_candidates:
        suggestion = rakuten_candidates[0]
        imported = request_json(
            "POST",
            f"{args.api}/closet/import-suggestion",
            body={"sessionId": session_id, "candidateId": candidate_id(suggestion)},
            headers={**auth_header, "Content-Type": "application/json"},
        )
        imported_item_id = imported["item_id"]
        if imported["ownershipStatus"] != "INTERESTING" or imported["status"] != "READY":
            raise RuntimeError(f"Unexpected import response: {imported}")
        document = firestore_closet_document(args, user_id, imported_item_id)
        if firestore_string(document, "ownershipStatus") != "INTERESTING":
            raise RuntimeError(f"Imported item not INTERESTING in Firestore: {document}")
        ownership_item_id = imported_item_id
    else:
        print("WARNING: no RAKUTEN candidates (credentials not configured?); "
              "exercising ownership transitions on the anchor item instead.")
        update_ownership(args, auth_header, anchor_id, "INTERESTING")
        ownership_item_id = anchor_id

    # Interesting -> Owned transition persists and keeps the item READY.
    updated = update_ownership(args, auth_header, ownership_item_id, "OWNED")
    if updated["ownershipStatus"] != "OWNED" or updated["status"] != "READY":
        raise RuntimeError(f"Ownership update failed: {updated}")
    document = firestore_closet_document(args, user_id, ownership_item_id)
    if firestore_string(document, "ownershipStatus") != "OWNED":
        raise RuntimeError(f"Ownership not persisted: {document}")

    selected_ids = [anchor_id] + (
        [candidate_id(rakuten_candidates[0])] if rakuten_candidates else []
    )
    run_generation(args, token, auth_header, session_id, selected_ids)

    # Reuse the (possibly imported) closet item through Standard CLOSET mode.
    reuse = request_json("POST", f"{args.api}/sessions", headers=auth_header)
    request_json(
        "POST",
        f"{args.api}/sessions/{reuse['session_id']}/source",
        body={
            "source": "CLOSET",
            "userPreference": {"style": "clean casual", "gender": "common"},
        },
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    reuse_events = stream_events(args, token, reuse["session_id"])
    if reuse_events[-1]["event"] != "session.proposed":
        raise RuntimeError(f"Standard CLOSET rerun did not propose: {reuse_events[-1]}")

    history = request_json("GET", f"{args.api}/sessions?limit=20", headers=auth_header)
    history_item = next(
        (item for item in history if item.get("session_id") == session_id), None
    )
    if history_item is None or not (history_item.get("style_result") or {}).get(
        "coordinate_image_url"
    ):
        raise RuntimeError(f"Assisted session missing from history: {history_item}")

    print(
        json.dumps(
            {
                "session_id": session_id,
                "user_id": user_id,
                "anchor_id": anchor_id,
                "candidate_count": len(candidates),
                "rakuten_candidate_count": len(rakuten_candidates),
                "imported_item_id": imported_item_id,
                "ownership_item_id": ownership_item_id,
                "history_coordinate_image_url": (
                    history_item.get("style_result") or {}
                ).get("coordinate_image_url"),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
