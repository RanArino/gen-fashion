"""ClosetAgent (M4-2, req §7.1)."""

from google.adk.agents import Agent

from ..config import get_settings
from ..tools.registry import registry

_INSTRUCTION = (
    "Search the user's closet or the shared closet for outfit items. "
    "The user message provides user_id, source (CLOSET or SHARED_CLOSET), and "
    "possibly sharedClosetId; always pass them to search_closet. Given clothing "
    "analysis results or an "
    "outfit request, generate a short description of each complementary item "
    "to find, then call search_closet once per garment type. Descriptions "
    "must use concrete garment nouns and attributes (e.g. 'casual shirt', "
    "'blue pants', 'sneakers'), not abstract phrases like 'spring outfit'. "
    "Use analyze_clothing_image when a garment image URL needs to be analyzed. "
    "Report the candidate items (including image_url and attribution) back."
)


def build_closet_agent() -> Agent:
    return Agent(
        name="ClosetAgent",
        model=get_settings().agent_model,
        description="Closet search & management sub-agent.",
        instruction=_INSTRUCTION,
        tools=[
            registry.get("analyze_clothing_image"),
            registry.get("search_closet"),
        ],
    )
