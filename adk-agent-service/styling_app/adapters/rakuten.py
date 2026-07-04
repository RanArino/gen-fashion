"""Rakuten Ichiba Item Search adapter (MK-3).

Wraps the official Ichiba Item Search API (2026-07-01 version). Requires
`rakuten_application_id` and `rakuten_access_key`; `rakuten_affiliate_id` is
optional and, when set, surfaces affiliate URLs in the results. When
credentials are absent the adapter raises RakutenUnavailableError so callers
can fall back to closet-only proposals.
"""

import httpx

from ..config import get_settings


class RakutenUnavailableError(RuntimeError):
    """Rakuten search cannot run (missing credentials or upstream failure)."""


def search_items(keyword: str, *, limit: int | None = None) -> list[dict]:
    """Run a keyword search and return raw item dicts.

    Each returned dict has: item_code, name, price, image_url, external_url,
    affiliate_url (may be None), shop_name.
    """
    settings = get_settings()
    if not settings.rakuten_application_id or not settings.rakuten_access_key:
        raise RakutenUnavailableError(
            "Rakuten credentials are not configured "
            "(RAKUTEN_APPLICATION_ID / RAKUTEN_ACCESS_KEY)"
        )
    params = {
        "applicationId": settings.rakuten_application_id,
        "accessKey": settings.rakuten_access_key,
        "keyword": keyword,
        "hits": min(limit or settings.rakuten_max_results, settings.rakuten_max_results),
        "formatVersion": 2,
    }
    if settings.rakuten_affiliate_id:
        params["affiliateId"] = settings.rakuten_affiliate_id
    # The 2026 endpoint validates Origin/Referer even server-to-server and
    # returns 403 REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING without them.
    app_url = settings.rakuten_application_url
    headers = {
        "Origin": app_url.rstrip("/"),
        "Referer": app_url,
    }
    try:
        response = httpx.get(
            settings.rakuten_search_endpoint,
            params=params,
            headers=headers,
            timeout=settings.rakuten_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        raise RakutenUnavailableError(f"Rakuten search failed: {exc}") from exc

    items = []
    for entry in payload.get("Items") or []:
        # formatVersion=1 wraps each entry as {"Item": {...}}; 2 is flat.
        item = entry.get("Item") if isinstance(entry, dict) and "Item" in entry else entry
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "item_code": item.get("itemCode"),
                "name": item.get("itemName"),
                "price": item.get("itemPrice"),
                "image_url": _first_image_url(item),
                "external_url": item.get("itemUrl"),
                "affiliate_url": item.get("affiliateUrl") or None,
                "shop_name": item.get("shopName"),
            }
        )
    return items


def _first_image_url(item: dict) -> str | None:
    for field in ("mediumImageUrls", "smallImageUrls"):
        urls = item.get(field) or []
        for url in urls:
            # formatVersion=1 uses {"imageUrl": "..."}; 2 uses plain strings.
            if isinstance(url, dict):
                url = url.get("imageUrl")
            if url:
                # Thumbnails default to 128x128 via the `_ex` size parameter;
                # request 400x400 so candidate cards are not blurry.
                return str(url).replace("_ex=128x128", "_ex=400x400")
    return None
