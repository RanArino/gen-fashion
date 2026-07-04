"""Agent topology tests (M4-1/2/3): wiring only, no model calls."""

from styling_app.agent import build_agent_for_phase, root_agent
from styling_app.agents import build_closet_agent, build_styling_agent


def _tool_names(agent):
    return [getattr(tool, "__name__", getattr(tool, "name", None)) for tool in agent.tools]


def test_root_agent_topology():
    assert root_agent.name == "styling_app"
    assert [a.name for a in root_agent.sub_agents] == ["ClosetAgent", "StylingAgent"]


def test_closet_agent_toolset():
    agent = build_closet_agent()
    assert _tool_names(agent) == ["analyze_clothing_image", "search_closet"]


def test_closet_agent_standard_mode_has_no_rakuten_tool():
    agent = build_closet_agent()
    assert "search_rakuten" not in _tool_names(agent)


def test_closet_agent_assisted_mode_adds_rakuten_tool():
    agent = build_closet_agent(assisted=True)
    assert _tool_names(agent) == [
        "analyze_clothing_image",
        "search_closet",
        "search_rakuten",
    ]


def test_assisted_propose_agent_tree_still_withholds_generation():
    propose_agent = build_agent_for_phase("propose", assisted=True)

    def all_tool_names(agent):
        names = _tool_names(agent)
        for sub_agent in agent.sub_agents:
            names.extend(all_tool_names(sub_agent))
        return names

    names = all_tool_names(propose_agent)
    assert "search_rakuten" in names
    assert "style_synthesizer" not in names


def test_styling_agent_toolset():
    agent = build_styling_agent()
    assert _tool_names(agent) == ["ask_preference", "style_synthesizer"]


def test_propose_agent_tree_physically_withholds_generation():
    propose_agent = build_agent_for_phase("propose")

    def all_tool_names(agent):
        names = _tool_names(agent)
        for sub_agent in agent.sub_agents:
            names.extend(all_tool_names(sub_agent))
        return names

    assert [agent.name for agent in propose_agent.sub_agents] == ["ClosetAgent"]
    assert "search_closet" in all_tool_names(propose_agent)
    assert "style_synthesizer" not in all_tool_names(propose_agent)


def test_generate_phase_uses_generation_enabled_styling_agent():
    generate_agent = build_agent_for_phase("generate")

    assert generate_agent.name == "StylingAgent"
    assert _tool_names(generate_agent) == ["ask_preference", "style_synthesizer"]


def test_generate_phase_uses_injected_constrained_style_tool():
    def constrained_style_synthesizer(style_description: str = "") -> dict:
        return {}

    constrained_style_synthesizer.__name__ = "style_synthesizer"
    generate_agent = build_agent_for_phase(
        "generate", style_tool=constrained_style_synthesizer
    )

    assert _tool_names(generate_agent) == ["ask_preference", "style_synthesizer"]
    style_tool = generate_agent.tools[-1]
    assert style_tool is constrained_style_synthesizer
