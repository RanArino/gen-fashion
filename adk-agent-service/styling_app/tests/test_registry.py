import pytest

from styling_app.tools.registry import ToolRegistry, registry


def test_register_and_get():
    reg = ToolRegistry()

    def my_tool():
        return "ok"

    reg.register("my_tool", my_tool)
    assert reg.get("my_tool") is my_tool
    assert reg.all() == {"my_tool": my_tool}


def test_duplicate_registration_rejected():
    reg = ToolRegistry()
    reg.register("t", lambda: None)
    with pytest.raises(ValueError):
        reg.register("t", lambda: None)


def test_unknown_tool_raises():
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")


def test_all_four_m4_tools_registered():
    import styling_app.tools  # noqa: F401  (import populates the registry)

    names = set(registry.all())
    assert {
        "analyze_clothing_image",
        "search_closet",
        "search_rakuten",
        "style_synthesizer",
        "ask_preference",
    } <= names
