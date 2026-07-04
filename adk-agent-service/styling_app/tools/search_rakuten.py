"""search_rakuten tool (MK-3, req-phase02 shopping-aided coordination).

Searches Rakuten Ichiba for purchasable clothes and accessories and returns
CandidateItem-shaped dicts so the propose phase can mix them with closet
candidates. Kept separate from search_closet: different credentials,
rate limits, fields, and attribution (ADL: MK Decision Log).
"""

from ..adapters import rakuten
from .registry import registry

RAKUTEN_ATTRIBUTION = "Rakuten Ichiba"


def search_rakuten(
    query: str,
    category: str | None = None,
    colors: list[str] | None = None,
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
        limit: Maximum number of items to return.

    Returns:
        List of candidate items: {item_id, source, name, image_url, price,
        category, tags, external_url, affiliate_url, shop_name, attribution}.
    """
    keyword = " ".join([query, *(colors or [])]).strip()
    if not keyword:
        raise ValueError("query must not be empty")
    items = rakuten.search_items(keyword, limit=limit)
    results = []
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
                "tags": list(colors or []),
                "external_url": item.get("external_url"),
                "affiliate_url": item.get("affiliate_url"),
                "shop_name": item.get("shop_name"),
                "attribution": RAKUTEN_ATTRIBUTION,
            }
        )
    return results[:limit]


registry.register("search_rakuten", search_rakuten)
