"""Hybrid search over the clothing_items index (M4-6).

Queries the index owned by fastapi-service (M2-9 mapping, M3-2 shared seed).
Keyword-first with an additive, fail-soft kNN clause (M1-3 re-scope): on any
kNN error the query is retried keyword-only. The keyword shape mirrors the
M3-3 SharedClosetSearchAdapter (match on tags/category, filter on user_id).
"""

import re
from functools import lru_cache

from elasticsearch import Elasticsearch

from ..config import get_settings


@lru_cache
def _client() -> Elasticsearch:
    settings = get_settings()
    kwargs = {"hosts": [settings.elasticsearch_url]}
    if settings.elasticsearch_ca_certs:
        kwargs["ca_certs"] = settings.elasticsearch_ca_certs
    if settings.elasticsearch_ssl_assert_fingerprint:
        kwargs["ssl_assert_fingerprint"] = settings.elasticsearch_ssl_assert_fingerprint
    if settings.elasticsearch_api_key:
        kwargs["api_key"] = settings.elasticsearch_api_key
    return Elasticsearch(**kwargs)


def hybrid_search(
    *,
    user_id: str,
    description: str,
    query_vector: list[float] | None = None,
    category: str | list[str] | None = None,
    colors: list[str] | None = None,
    closet_id: str | None = None,
    gender: str | None = None,
    intent: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Return raw hits [{item_id, ...doc fields}] for the closet of `user_id`."""
    settings = get_settings()
    user_filter = {"term": {"user_id": user_id}}

    # tags/category/colors are keyword fields (M2-9 mapping) and the M3 seed
    # capitalizes categories ("Pants"), so the description is tokenized and
    # matched with case-insensitive term queries instead of `match`.
    bool_query: dict = {"filter": [user_filter]}
    if closet_id:
        bool_query["filter"].append({"term": {"closetId": closet_id}})
    if category:
        categories = [category] if isinstance(category, str) else category
        bool_query["filter"].append(
            {
                "bool": {
                    "should": [_ci_term("category", value) for value in categories],
                    "minimum_should_match": 1,
                }
            }
        )
    if colors:
        bool_query["filter"].append(
            {"bool": {"should": [_ci_term("colors", c) for c in colors],
                      "minimum_should_match": 1}}
        )
    if gender:
        bool_query.setdefault("should", []).extend(
            [_ci_term("gender", gender), _ci_term("gender", "common")]
        )
    if intent and settings.intent_boost_enabled:
        # MR-6: opt-in preference signal, not a filter — most items carry no
        # intentTags, so this must only ever raise the score of a match, never
        # narrow the result set. Lands in `should` and must never touch
        # `minimum_should_match` (Decision Log; boost, not filter).
        clause = _ci_term("intentTags", intent)
        clause["term"]["intentTags"]["boost"] = settings.intent_boost_weight
        bool_query.setdefault("should", []).append(clause)
    should = [
        _ci_term(field, token)
        for token in re.findall(r"[a-z0-9]+", description.lower())
        for field in ("tags", "category", "colors", "season")
    ]
    if should:
        bool_query.setdefault("should", []).extend(should)
        bool_query["minimum_should_match"] = 1
    query = {"bool": bool_query}

    if query_vector is not None:
        try:
            response = _client().search(
                index=settings.clothing_items_index,
                size=limit,
                query=query,
                knn={
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": limit,
                    "num_candidates": max(50, limit * 5),
                    "filter": [user_filter],
                },
            )
            return _hits(response)
        except Exception:
            pass  # fail-soft: degrade to keyword-only (Decision Log; M1-3)

    response = _client().search(
        index=settings.clothing_items_index,
        size=limit,
        query=query,
    )
    return _hits(response)


def _ci_term(field: str, value: str) -> dict:
    return {"term": {field: {"value": value, "case_insensitive": True}}}


def _hits(response) -> list[dict]:
    return [
        {"item_id": hit["_id"], **hit.get("_source", {})}
        for hit in response["hits"]["hits"]
    ]
