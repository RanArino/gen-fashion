"""ADK entry point: `adk web` / `adk api_server` discover `root_agent` here."""

from collections.abc import Callable

from google.adk.agents import Agent

from .agents.orchestrator import build_orchestrator
from .agents.styling_agent import build_styling_agent


def build_agent_for_phase(
    phase: str,
    *,
    search_tool: Callable | None = None,
    style_tool: Callable | None = None,
) -> Agent:
    if phase == "propose":
        return build_orchestrator(
            include_generation=False,
            search_tool=search_tool,
        )
    if phase == "generate":
        return build_styling_agent(include_generation=True, style_tool=style_tool)
    raise ValueError(f"Unsupported run phase: {phase}")

root_agent = build_orchestrator()
