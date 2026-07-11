#!/usr/bin/env python3
"""MO-6 manual visual check: scene-aware style synthesizer prompt.

Runs one real, live Assisted Coordinate session against Rakuten (requires
`RAKUTEN_APPLICATION_ID`/`RAKUTEN_ACCESS_KEY` and real Vertex AI
credentials -- both already configured in this repo's local `.env` /
`adk-agent-service/.env`), and, unlike `mk_assisted_coordinate_smoke.py`
(which selects only the first Rakuten candidate), selects several distinct
Rakuten-sourced candidates so the single generation call mixes multiple
real-world Rakuten photo types (plain product shot, worn-by-a-model,
held-in-hand-among-props) in one output. This reproduces the conditions
`docs/local/20260704_styling_image_generation_issue.md` and
`docs/plans/20260704-mo-style-synthesizer-scene-aware-prompt.md`'s MO-6
describe without needing three hand-crafted input files -- real Rakuten
listings naturally include this mix of photo types.

Downloads each selected Rakuten candidate's source photo plus the final
generated coordinate image into --evidence-dir so they can be visually
compared: does the generated coordinate keep only the intended garments'
color/pattern/shape, without the original model's face/pose, street
background, or unrelated props leaking into the output?

Reuses request/auth/upload/streaming helpers from
`mk_assisted_coordinate_smoke.py` (same directory) rather than duplicating
them.
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mk_assisted_coordinate_smoke as mk  # noqa: E402


def download(url: str, path: Path) -> None:
    with urlopen(url, timeout=30) as response:
        path.write_bytes(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live MO-6 Assisted Coordinate visual check.")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--auth-emulator", default="http://localhost:9099")
    parser.add_argument("--firestore-emulator", default="http://localhost:8080")
    parser.add_argument("--project", default="gen-fashion-local")
    parser.add_argument("--storage-endpoint", default="http://localhost:9000")
    parser.add_argument("--storage-access-key", default="minioadmin")
    parser.add_argument("--storage-secret-key", default="minioadmin")
    parser.add_argument("--bucket", default="gen-fashion-images")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--max-rakuten-items", type=int, default=3)
    parser.add_argument("--evidence-dir", default="/tmp/mo6-evidence")
    args = parser.parse_args()

    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)

    mk.ensure_bucket(args)
    token, user_id = mk.auth_token(args)
    auth_header = {"Authorization": f"Bearer {token}"}

    anchor_id, _ = mk.upload_ready_anchor(args, auth_header, user_id)
    print(f"anchor_id={anchor_id}")

    created = mk.request_json("POST", f"{args.api}/sessions", headers=auth_header)
    assisted = mk.request_json(
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
    session_id = assisted["session_id"]
    print(f"session_id={session_id}")

    propose_events = mk.stream_events(args, token, session_id)
    proposed = propose_events[-1]
    if proposed["event"] != "session.proposed":
        raise RuntimeError(f"Assisted session did not pause for selection: {proposed}")
    candidates = proposed["data"].get("candidates", [])
    rakuten_candidates = [c for c in candidates if c.get("source") == "RAKUTEN"]
    if not rakuten_candidates:
        raise RuntimeError(
            "No RAKUTEN candidates in the assisted proposal (live credentials required)"
        )
    print(f"total_candidates={len(candidates)} rakuten_candidates={len(rakuten_candidates)}")

    # Prefer one candidate per distinct category for photo-type variety
    # (a product shot, a worn-on-model shot, a held-in-hand shot are more
    # likely to appear across *different* real Rakuten listings than within
    # one). Fall back to just taking the first few if categories collapse.
    chosen = []
    seen_categories = set()
    for c in rakuten_candidates:
        cat = c.get("category")
        if cat in seen_categories:
            continue
        chosen.append(c)
        seen_categories.add(cat)
        if len(chosen) >= args.max_rakuten_items:
            break
    if len(chosen) < min(2, len(rakuten_candidates)):
        chosen = rakuten_candidates[: args.max_rakuten_items]

    print("chosen Rakuten candidates:")
    manifest = []
    for i, c in enumerate(chosen):
        cid = mk.candidate_id(c)
        info = {
            "item_id": cid,
            "category": c.get("category"),
            "name": c.get("name"),
            "image_url": c.get("image_url") or c.get("imageUrl"),
        }
        manifest.append(info)
        print(f"  [{i}] {info}")
        img_url = info["image_url"]
        if img_url:
            try:
                download(img_url, evidence / f"source_{i}_{cid.replace(':', '_')}.jpg")
            except Exception as exc:  # noqa: BLE001
                print(f"    WARNING: failed to download source photo: {exc}")

    (evidence / "candidates.json").write_text(json.dumps(manifest, indent=2))

    selected_ids = [anchor_id] + [mk.candidate_id(c) for c in chosen]
    print(f"selected_ids={selected_ids}")

    mk.request_json(
        "POST",
        f"{args.api}/sessions/{session_id}/select",
        body={"selectedItemIds": selected_ids},
        headers={**auth_header, "Content-Type": "application/json"},
        expected=(202,),
    )
    events = mk.stream_events(args, token, session_id)
    terminal = events[-1]
    print(f"terminal_event={terminal['event']} data={terminal['data']}")
    if terminal["event"] != "session.completed":
        raise RuntimeError(f"Session did not complete: {terminal}")

    session_doc = mk.request_json(
        "GET", f"{args.api}/sessions/{session_id}", headers=auth_header
    )
    image_url = (session_doc.get("style_result") or {}).get("coordinate_image_url")
    if not image_url:
        raise RuntimeError(f"No coordinate_image_url after completion: {session_doc}")
    download(image_url, evidence / "generated_coordinate.jpg")
    print(f"generated_coordinate_image={evidence / 'generated_coordinate.jpg'}")

    summary = {
        "session_id": session_id,
        "user_id": user_id,
        "anchor_id": anchor_id,
        "chosen_rakuten_candidates": manifest,
        "coordinate_image_url": image_url,
    }
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
