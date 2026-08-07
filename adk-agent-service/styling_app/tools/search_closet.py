"""search_closet tool (M4-6, req §6.3/§7.2/§8.3).

The agent supplies a natural-language description of complementary items; the
tool embeds it (fail-soft) and runs the keyword-first hybrid query. Returns
CandidateItem-shaped dicts. SHARED_CLOSET results carry the CC BY-SA 4.0
attribution (M3-3 parity, req §16.3) and can be filtered by the selected
demo closet. RAKUTEN is Phase 1b — not wired here.
"""

from ..adapters import elasticsearch, gemini, image_storage
from .registry import registry

SHARED_USER_ID = "__shared__"
SHARED_ATTRIBUTION = "Clothing Dataset (CC BY-SA 4.0)"
_CATEGORY_ALIASES = {
    "top": ["Top", "Shirt", "Blouse", "Polo", "T-Shirt", "Longsleeve", "Hoodie"],
    "tops": ["Top", "Shirt", "Blouse", "Polo", "T-Shirt", "Longsleeve", "Hoodie"],
    "bottom": ["Pants", "Shorts", "Skirt"],
    "bottoms": ["Pants", "Shorts", "Skirt"],
    "pants": ["Pants"],
    "jeans": ["Pants"],
    "shoes": ["Shoes"],
    "hat": ["Hat"],
    "outer": ["Blazer", "Outwear"],
    "outerwear": ["Blazer", "Outwear"],
}


def search_closet(
    description: str,
    source: str,
    user_id: str,
    shared_closet_id: str | None = None,
    category: str | None = None,
    colors: list[str] | None = None,
    gender: str | None = None,
    intent: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search the user's closet or the shared closet for matching items.

    Args:
        description: Natural-language description of the items to find; use
            concrete garment nouns, colors, and seasons (e.g. "casual navy
            pants", "summer dress"), not abstract phrases like "cute outfit".
        source: "CLOSET" (the user's own items) or "SHARED_CLOSET" (demo data).
        user_id: ID of the requesting user.
        shared_closet_id: Optional demo closet filter (e.g. "adult-01").
        category: Optional exact category filter (e.g. "pants").
        colors: Optional color filter.
        gender: Optional wearer gender preference; matching/common items are boosted.
        intent: Optional preference signal for the state the user wants to feel
            while wearing the result (e.g. "CONFIDENT", "AT_EASE"). Items
            carrying this intent tag are ranked higher; it never excludes
            items without it, so omitting it is fine and should not be a
            reason to skip searching.
        limit: Maximum number of items to return.

    Returns:
        List of candidate items: {item_id, source, image_url, category, tags,
        attribution}. attribution is set for SHARED_CLOSET items.
    """
    if source not in ("CLOSET", "SHARED_CLOSET"):
        raise ValueError(
            f"Unsupported source: {source!r} (RAKUTEN is Phase 1b; "
            "use CLOSET or SHARED_CLOSET)"
        )
    es_user_id = SHARED_USER_ID if source == "SHARED_CLOSET" else user_id

    # kNN is additive: keyword results are the bar (M1-3), so embedding
    # failures must not fail the search. Locally the shared docs carry no
    # embedding vectors, so the kNN clause is inert for SHARED_CLOSET.
    try:
        query_vector = gemini.embed_text(description) if description else None
    except Exception:
        query_vector = None

    hits = elasticsearch.hybrid_search(
        user_id=es_user_id,
        description=description,
        query_vector=query_vector,
        category=_normalize_category(category),
        colors=colors,
        closet_id=shared_closet_id if source == "SHARED_CLOSET" else None,
        gender=gender,
        intent=intent,
        limit=limit,
    )

    results = []
    for hit in hits:
        item_id = hit["item_id"]
        image_key = hit.get("imageUrl") or f"{es_user_id}/closet/{item_id}.jpg"
        try:
            image_url = image_storage.get_download_url(image_key)
        except Exception:
            image_url = ""
        results.append(
            {
                "item_id": item_id,
                "source": source,
                "image_url": image_url,
                "category": hit.get("category"),
                "tags": hit.get("tags", []),
                "colors": hit.get("colors", []),
                "season": hit.get("season"),
                "gender": hit.get("gender", "common"),
                "attribution": SHARED_ATTRIBUTION if source == "SHARED_CLOSET" else None,
            }
        )
    return results


def _normalize_category(category: str | None) -> str | list[str] | None:
    if not category:
        return None
    return _CATEGORY_ALIASES.get(category.lower(), category)


registry.register("search_closet", search_closet)
