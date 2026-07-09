"""search_rakuten tool (MK-3, req-phase02 shopping-aided coordination).

Searches Rakuten Ichiba for purchasable clothes and accessories and returns
CandidateItem-shaped dicts so the propose phase can mix them with closet
candidates. Kept separate from search_closet: different credentials,
rate limits, fields, and attribution (ADL: MK Decision Log).
"""

from ..adapters import rakuten
from .registry import registry

RAKUTEN_ATTRIBUTION = "Rakuten Ichiba"

_CATEGORY_KEYWORDS = {
    "top": "トップス",
    "shirt": "シャツ",
    "bottom": "パンツ",
    "pants": "パンツ",
    "shoes": "靴",
    "shoe": "靴",
    "bag": "バッグ",
    "hat": "帽子",
    "belt": "ベルト",
    "outer": "ジャケット",
    "outerwear": "ジャケット",
    "accessory": "アクセサリー",
}

_COLOR_KEYWORDS = {
    "black": "黒",
    "white": "白",
    "blue": "青",
    "navy": "ネイビー",
    "red": "赤",
    "green": "緑",
    "yellow": "黄",
    "brown": "茶",
    "beige": "ベージュ",
    "gray": "グレー",
    "grey": "グレー",
    "pink": "ピンク",
    "purple": "紫",
}

_COLOR_TAG_ALIASES = {
    **{color: color for color in _COLOR_KEYWORDS},
    "黒": "black",
    "白": "white",
    "青": "blue",
    "赤": "red",
    "緑": "green",
    "黄": "yellow",
    "茶": "brown",
    "茶色": "brown",
    "ベージュ": "beige",
    "グレー": "gray",
    "灰色": "gray",
    "ネイビー": "navy",
    "紺": "navy",
    "ピンク": "pink",
    "紫": "purple",
    "grey": "gray",
}


def search_rakuten(
    query: str,
    category: str | None = None,
    colors: list[str] | None = None,
    tags: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search Rakuten Ichiba for purchasable items and accessories.

    Args:
        query: Concrete Japanese or English item description to search for;
            use garment/accessory nouns with attributes (e.g. "white t-shirt",
            "black leather belt"), not abstract phrases.
        category: Optional category hint recorded on the results (e.g. "hat",
            "bag", "shoes", "top").
        colors: Optional colors appended to the search keyword.
        tags: Optional English metadata tags for the intended item, such as
            garment type, material, fit, formality, season, or style. These are
            saved on returned candidates and do not need to be repeated in the
            Rakuten query.
        limit: Maximum number of items to return.

    Returns:
        List of candidate items: {item_id, source, name, image_url, price,
        category, tags, external_url, affiliate_url, shop_name, attribution}.
    """
    keywords = _search_keywords(query, category=category, colors=colors)
    if not keywords:
        raise ValueError("query must not be empty")
    results_by_id = {}
    for keyword in keywords:
        items = rakuten.search_items(keyword, limit=limit)
        for result in _candidate_results(
            items,
            category=category,
            colors=colors,
            tags=tags,
        ):
            results_by_id.setdefault(result["item_id"], result)
            if len(results_by_id) >= limit:
                return list(results_by_id.values())
    return list(results_by_id.values())


def _candidate_results(
    items: list[dict],
    *,
    category: str | None,
    colors: list[str] | None,
    tags: list[str] | None,
) -> list[dict]:
    results = []
    candidate_tags = _metadata_tags(colors=colors, tags=tags)
    for item in items:
        if not item.get("item_code") or not item.get("image_url"):
            continue
        results.append(
            {
                "item_id": f"rakuten:{item['item_code']}",
                "source": "RAKUTEN",
                "name": item.get("name"),
                "image_url": item["image_url"],
                "price": item.get("price"),
                "category": category,
                "tags": candidate_tags,
                "external_url": item.get("external_url"),
                "affiliate_url": item.get("affiliate_url"),
                "shop_name": item.get("shop_name"),
                "attribution": RAKUTEN_ATTRIBUTION,
            }
        )
    return results


def _metadata_tags(
    *,
    colors: list[str] | None,
    tags: list[str] | None,
) -> list[str]:
    normalized: list[str] = []
    for value in [*(colors or []), *(tags or [])]:
        tag = _normalize_metadata_tag(value)
        if tag and tag not in normalized:
            normalized.append(tag)
    return normalized


def _normalize_metadata_tag(value: str) -> str | None:
    normalized = " ".join(str(value).strip().lower().split())
    if not normalized:
        return None
    return _COLOR_TAG_ALIASES.get(normalized, normalized)


def _search_keywords(
    query: str,
    *,
    category: str | None,
    colors: list[str] | None,
) -> list[str]:
    """Prefer the agent's concrete query, then broaden for Rakuten recall."""
    color_terms = [_keyword_for_color(color) for color in colors or []]
    category_term = _keyword_for_category(category)
    raw_keywords = [
        " ".join([query, *(colors or [])]),
        query,
        " ".join([*color_terms, category_term or ""]),
        category_term or "",
    ]
    keywords = []
    for keyword in raw_keywords:
        normalized = " ".join(keyword.split())
        if normalized and normalized not in keywords:
            keywords.append(normalized)
    return keywords


def _keyword_for_category(category: str | None) -> str | None:
    if category is None:
        return None
    return _CATEGORY_KEYWORDS.get(category.strip().lower(), category.strip() or None)


def _keyword_for_color(color: str) -> str:
    normalized = color.strip().lower()
    return _COLOR_KEYWORDS.get(normalized, color.strip())


registry.register("search_rakuten", search_rakuten)
