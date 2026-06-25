"""StylingAgent (M4-3, req §7.1)."""

from google.adk.agents import Agent

from ..config import get_settings
from ..tools.registry import registry

_INSTRUCTION = (
    "Collect user preferences and generate the final coordinate image. "
    "Call ask_preference with any preferences stated in the conversation to "
    "normalize them. Once candidate items are chosen, call style_synthesizer "
    "with the user_id, the selected item image URLs, and a style description; "
    "return the coordinate_image_url and which items were used."
)


def build_styling_agent() -> Agent:
    return Agent(
        name="StylingAgent",
        model=get_settings().agent_model,
        description="Coordination generation & proposal sub-agent.",
        instruction=_INSTRUCTION,
        tools=[
            registry.get("ask_preference"),
            registry.get("style_synthesizer"),
        ],
    )
