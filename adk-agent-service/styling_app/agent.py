"""ADK entry point: `adk web` / `adk api_server` discover `root_agent` here."""

from .agents.orchestrator import build_orchestrator

root_agent = build_orchestrator()
