"""StylingAgent (M4-3, req §7.1)."""

from collections.abc import Callable

from google.adk.agents import Agent

from ..config import get_settings
from ..tools.registry import registry

_BASE_INSTRUCTION = (
    "Collect and normalize user preferences. Call ask_preference with any "
    "preferences stated in the conversation. "
)
_GENERATION_INSTRUCTION = (
    "The user message contains explicitly selected item image URLs. Call "
    "style_synthesizer with exactly those URLs, the user_id, style description, "
    "wearer gender, and wearer age (adult or child); return the "
    "coordinate_image_url and which items were used."
)
_CONSTRAINED_GENERATION_INSTRUCTION = (
    "The server has already fixed the selected garments, the requesting user, "
    "the wearer gender, and the wearer age for this run. Call style_synthesizer "
    "to produce the coordinate image; the only argument you may set is an "
    "optional style_description that summarizes the desired styling direction. "
    "Return the coordinate_image_url and which items were used."
)
_PROPOSAL_INSTRUCTION = (
    "This is a proposal-only run. Help normalize preferences when requested, "
    "but do not generate a coordinate image."
)


def build_styling_agent(
    include_generation: bool = True,
    *,
    style_tool: Callable | None = None,
) -> Agent:
    tools = [registry.get("ask_preference")]
    if include_generation:
        tools.append(style_tool or registry.get("style_synthesizer"))
    if not include_generation:
        generation_instruction = _PROPOSAL_INSTRUCTION
    elif style_tool is not None:
        generation_instruction = _CONSTRAINED_GENERATION_INSTRUCTION
    else:
        generation_instruction = _GENERATION_INSTRUCTION
    return Agent(
        name="StylingAgent",
        model=get_settings().agent_model,
        description="Coordination generation & proposal sub-agent.",
        instruction=_BASE_INSTRUCTION + generation_instruction,
        tools=tools,
    )
