"""StylingOrchestratorAgent (M4-1, req §7.1).

A2A-ready discipline (ADL-019): session_id/user_id/source arrive in the
initial user message, tools fetch their own data, no shared in-memory state
across agents, and each sub-agent owns its toolset.
"""

from collections.abc import Callable

from google.adk.agents import Agent

from ..config import get_settings
from .closet_agent import build_closet_agent
from .styling_agent import build_styling_agent

_INSTRUCTION = (
    "You coordinate outfit suggestions. The user message provides user_id, "
    "source (CLOSET or SHARED_CLOSET), possibly sharedClosetId, and user "
    "preferences including gender; include them when delegating. "
)
_GENERATION_INSTRUCTION = (
    "Delegate closet/shared-closet search tasks to ClosetAgent and require it "
    "to pass the gender preference to search_closet. Delegate preference "
    "handling and coordinate image generation to StylingAgent."
)
_PROPOSAL_INSTRUCTION = (
    "This is a proposal-only run. Delegate only to ClosetAgent, require it to "
    "pass the gender preference to search_closet, let it write concrete descriptions "
    "for complementary garment searches, and return the candidate items."
)


def build_orchestrator(
    include_generation: bool = True,
    search_tool: Callable | None = None,
    rakuten_tool: Callable | None = None,
    assisted: bool = False,
) -> Agent:
    sub_agents = [
        build_closet_agent(
            search_tool=search_tool, rakuten_tool=rakuten_tool, assisted=assisted
        )
    ]
    if include_generation:
        sub_agents.append(build_styling_agent(include_generation=True))
    return Agent(
        name="styling_app",
        model=get_settings().agent_model,
        description="Root orchestrator for outfit coordination.",
        instruction=_INSTRUCTION
        + (_GENERATION_INSTRUCTION if include_generation else _PROPOSAL_INSTRUCTION),
        sub_agents=sub_agents,
    )
