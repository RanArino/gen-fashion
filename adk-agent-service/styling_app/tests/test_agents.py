"""Agent topology tests (M4-1/2/3): wiring only, no model calls."""

from styling_app.agent import root_agent
from styling_app.agents import build_closet_agent, build_styling_agent


def _tool_names(agent):
    return [getattr(tool, "__name__", getattr(tool, "name", None)) for tool in agent.tools]


def test_root_agent_topology():
    assert root_agent.name == "styling_app"
    assert [a.name for a in root_agent.sub_agents] == ["ClosetAgent", "StylingAgent"]


def test_closet_agent_toolset():
    agent = build_closet_agent()
    assert _tool_names(agent) == ["analyze_clothing_image", "search_closet"]


def test_styling_agent_toolset():
    agent = build_styling_agent()
    assert _tool_names(agent) == ["ask_preference", "style_synthesizer"]
