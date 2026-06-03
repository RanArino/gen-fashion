#!/usr/bin/env python3
"""
M1-4 ADK Event Stream Granularity PoC — gen-fashion

Runs a minimal Google ADK agent turn that triggers one tool call and captures
every event yielded by runner.run_async(). The results inform the Firestore
relay design in ADL-011 and the agentEvents Firestore schema for M5-8.

Usage:
    pip install -r requirements.txt
    cp .env.example .env          # fill in GOOGLE_CLOUD_PROJECT
    python run_poc.py

Auth: gcloud auth application-default login

Outputs:
    sample_events.jsonl   — one JSON object per line, each event captured
                            Commit this file to git after running.

Questions this PoC answers (fill in M1 ExecPlan Artifacts after running):
  1. What distinct event type names appear?
  2. Are tokens streamed as partial events or batched into one response event?
  3. How many events occur for one turn (reason → tool call → reason → answer)?
  4. Is each event directly JSON-serialisable, or does it need custom handling?
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

_HERE = Path(__file__).parent
load_dotenv(_HERE / ".env")

EVENTS_FILE = _HERE / "sample_events.jsonl"

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.0-flash")


# ── Stub tool ──────────────────────────────────────────────────────────────────

def get_clothing_tags(item_id: str) -> dict:
    """
    Stub tool: returns fixed clothing metadata for a given item ID.
    Used so the agent must reason, call this tool, then answer — producing
    at least one ToolCall and one ToolResult event in the stream.
    """
    return {
        "item_id": item_id,
        "category": "shirt",
        "color": "navy blue",
        "tags": ["casual", "cotton", "slim-fit"],
        "season": "spring/summer",
    }


# ── Event capture ──────────────────────────────────────────────────────────────

def _serialize_event(event) -> dict:
    """
    Attempt to produce a JSON-serialisable representation of an ADK event.
    Tries model_dump() first (Pydantic), then to_dict(), then vars(), then str().
    The serialisation approach used is recorded so ADL-011 knows whether a
    transformation step is needed before writing events to Firestore.
    """
    strategies = [
        ("model_dump", lambda e: e.model_dump() if hasattr(e, "model_dump") else None),
        ("to_dict",    lambda e: e.to_dict()    if hasattr(e, "to_dict")    else None),
        ("vars",       lambda e: {k: str(v) for k, v in vars(e).items() if not k.startswith("_")}
                                if hasattr(e, "__dict__") else None),
        ("repr",       lambda e: repr(e)),
    ]

    for strategy_name, fn in strategies:
        try:
            result = fn(event)
            if result is not None:
                json.dumps(result, default=str)  # verify serialisability
                return {"_serialisation": strategy_name, "data": result}
        except Exception:
            continue

    return {"_serialisation": "fallback_str", "data": str(event)}


async def run_and_capture() -> None:
    # Import ADK here so import errors surface cleanly with a useful message.
    try:
        from google.adk.agents import Agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types
    except ImportError as exc:
        sys.exit(
            f"ERROR: google-adk is not installed ({exc}).\n"
            "Run: pip install -r requirements.txt"
        )

    agent = Agent(
        name="styling_poc_agent",
        model=AGENT_MODEL,
        instruction=(
            "You are a fashion styling assistant. "
            "Use the get_clothing_tags tool to look up clothing item details, "
            "then answer the user's question based on the result."
        ),
        tools=[get_clothing_tags],
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="adk_event_stream_poc",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="adk_event_stream_poc",
        user_id="poc_user",
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(
            text="Look up the details for clothing item 'shirt-001' and describe what it is."
        )],
    )

    print(f"Model   : {AGENT_MODEL}")
    print(f"Project : {PROJECT}")
    print(f"Session : {session.id}")
    print()
    print("Running agent turn — capturing all events...\n")

    captured: list[dict] = []
    start = time.monotonic()

    async for event in runner.run_async(
        user_id="poc_user",
        session_id=session.id,
        new_message=user_message,
    ):
        event_type = type(event).__name__
        ts = datetime.now(timezone.utc).isoformat()
        serialised = _serialize_event(event)

        record = {
            "seq": len(captured) + 1,
            "type": event_type,
            "timestamp": ts,
            "serialisation_strategy": serialised["_serialisation"],
            "payload": serialised["data"],
        }

        # Identify notable flags on the event for quick scanning
        flags = []
        if hasattr(event, "is_final_response") and callable(event.is_final_response):
            if event.is_final_response():
                flags.append("FINAL_RESPONSE")
        if hasattr(event, "content") and event.content:
            flags.append("has_content")
        if hasattr(event, "actions") and event.actions:
            flags.append("has_actions")
        if flags:
            record["flags"] = flags

        captured.append(record)
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  [{len(captured):02d}] {event_type}{flag_str}")

    elapsed = time.monotonic() - start

    # Write sample_events.jsonl
    with EVENTS_FILE.open("w") as fh:
        for record in captured:
            fh.write(json.dumps(record, default=str) + "\n")

    # Count distinct event types
    type_counts: dict[str, int] = {}
    for r in captured:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1

    serialisation_strategies: set[str] = {r["serialisation_strategy"] for r in captured}

    print()
    print("─" * 60)
    print(f"Total events      : {len(captured)}")
    print(f"Elapsed           : {elapsed:.2f}s")
    print(f"Distinct types    : {sorted(type_counts.keys())}")
    print(f"Type counts       : {type_counts}")
    print(f"Serialisation     : {serialisation_strategies}")
    print()
    print(f"Event log written : {EVENTS_FILE}")
    print()
    print("Next steps:")
    print("  1. Commit sample_events.jsonl to git.")
    print("  2. Copy the findings above into the Artifacts section of:")
    print("     docs/plans/20260518-m1-poc-infrastructure-validation.md")
    print("  3. Answer the four schema questions in the plan (streaming, count, serialisation).")


def main() -> None:
    if not PROJECT:
        sys.exit(
            "ERROR: GOOGLE_CLOUD_PROJECT is not set.\n"
            "Copy .env.example to .env and fill in your GCP project ID."
        )
    asyncio.run(run_and_capture())


if __name__ == "__main__":
    main()
