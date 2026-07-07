"""ClosetAgent (M4-2, req §7.1)."""

from collections.abc import Callable

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
_ASSISTED_INSTRUCTION = (
    " This is an assisted-shopping run: the user message lists anchorItems the "
    "user already owns. Treat the anchor items as fixed context, describe a "
    "short styling suggestion for each missing garment or accessory (e.g. "
    "white t-shirt, black hat, bag, shoes, belt). The app generates only one "
    "coordinate at a time, so avoid proposing multiple auto-selected items for "
    "the same outfit slot; balance the look across missing categories such as "
    "bottoms, shoes, outerwear, and accessories based on the anchor categories. "
    "For Rakuten Ichiba, use search queries that work as marketplace keywords: "
    "prefer short Japanese product nouns plus one or two attributes (e.g. "
    "白 Tシャツ, 黒 パンツ, 革 ベルト), avoid overly narrow full outfit phrases, "
    "and pass a category hint such as top, bottom, shoes, bag, hat, belt, or "
    "outer. If a search is too narrow, retry with a broader category/product "
    "noun. Report both the anchor items and the purchasable Rakuten candidates "
    "(with name, price, image_url, category, and external_url) back."
)


def build_closet_agent(
    search_tool: Callable | None = None,
    rakuten_tool: Callable | None = None,
    assisted: bool = False,
) -> Agent:
    tools = [
        registry.get("analyze_clothing_image"),
        search_tool or registry.get("search_closet"),
    ]
    if assisted:
        tools.append(rakuten_tool or registry.get("search_rakuten"))
    return Agent(
        name="ClosetAgent",
        model=get_settings().agent_model,
        description="Closet search & management sub-agent.",
        instruction=_INSTRUCTION + (_ASSISTED_INSTRUCTION if assisted else ""),
        tools=tools,
    )
