"""StylingOrchestratorAgent (M4-1, req §7.1).

A2A-ready discipline (ADL-019): session_id/user_id/source arrive in the
initial user message, tools fetch their own data, no shared in-memory state
across agents, and each sub-agent owns its toolset.
"""

from google.adk.agents import Agent

from ..config import get_settings
from .closet_agent import build_closet_agent
from .styling_agent import build_styling_agent

_INSTRUCTION = (
    "You coordinate outfit suggestions. The user message provides user_id and "
    "source (CLOSET or SHARED_CLOSET); include them when delegating. Delegate "
    "to ClosetAgent for closet/shared-closet search tasks and to StylingAgent "
    "for preference handling and coordinate image generation."
)


def build_orchestrator() -> Agent:
    return Agent(
        name="styling_app",
        model=get_settings().agent_model,
        description="Root orchestrator for outfit coordination.",
        instruction=_INSTRUCTION,
        sub_agents=[build_closet_agent(), build_styling_agent()],
    )
