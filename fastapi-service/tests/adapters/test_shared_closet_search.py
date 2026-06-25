"""Unit tests for SharedClosetSearchAdapter (M3-3)."""
import pytest
from unittest.mock import AsyncMock, patch

from app.adapters.shared_closet_search import SharedClosetSearchAdapter
from app.domain.styling import CandidateItem, ClothingSource


class FakeImageStorage:
    async def get_download_url(self, image_path: str) -> str:
        return f"https://images.example.test/{image_path}"


def _make_es_hit(item_id: str, tags: list[str], category: str) -> dict:
    return {
        "_id": item_id,
        "_source": {
            "item_id": item_id,
            "user_id": "__shared__",
            "is_shared": True,
            "tags": tags,
            "category": category,
            "colors": ["white"],
            "season": "spring",
            "imageUrl": f"__shared__/closet/{item_id}.jpg",
        },
    }


def _make_es_response(hits: list[dict]) -> dict:
    return {"hits": {"hits": hits, "total": {"value": len(hits)}}}


@pytest.fixture
def adapter():
    with patch("app.adapters.shared_closet_search.AsyncElasticsearch") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        inst = SharedClosetSearchAdapter(image_storage=FakeImageStorage())
        inst._client = mock_client
        yield inst, mock_client


@pytest.mark.asyncio
async def test_search_by_source_returns_attributed_candidates(adapter):
    inst, mock_client = adapter
    hit = _make_es_hit("item-001", ["shirt", "casual"], "Shirt")
    mock_client.search.return_value = _make_es_response([hit])

    results = await inst.search_by_source(
        user_id="any-user",
        source=ClothingSource.SHARED_CLOSET,
        query="shirt",
        limit=5,
    )

    assert len(results) == 1
    item = results[0]
    assert isinstance(item, CandidateItem)
    assert item.item_id == "item-001"
    assert item.source == ClothingSource.SHARED_CLOSET
    assert item.attribution == "Clothing Dataset (CC BY-SA 4.0)"
    assert item.image_url == "https://images.example.test/__shared__/closet/item-001.jpg"
    assert "shirt" in item.tags


@pytest.mark.asyncio
async def test_search_by_source_wrong_source_raises_value_error(adapter):
    inst, _ = adapter
    with pytest.raises(ValueError):
        await inst.search_by_source(
            user_id="u", source=ClothingSource.CLOSET, query="shirt"
        )


@pytest.mark.asyncio
async def test_search_all_sources_includes_shared(adapter):
    inst, mock_client = adapter
    hit = _make_es_hit("item-002", ["dress"], "Dress")
    mock_client.search.return_value = _make_es_response([hit])

    results = await inst.search_all_sources(
        user_id="any",
        sources=[ClothingSource.SHARED_CLOSET, ClothingSource.CLOSET],
        query="dress",
    )

    assert len(results) == 1
    assert results[0].source == ClothingSource.SHARED_CLOSET


@pytest.mark.asyncio
async def test_search_non_empty_query_requires_keyword_match(adapter):
    inst, mock_client = adapter
    mock_client.search.return_value = _make_es_response([])
    await inst.search_by_source(
        user_id="u", source=ClothingSource.SHARED_CLOSET, query="shirt", limit=10
    )
    call_kwargs = mock_client.search.call_args.kwargs
    query = call_kwargs["query"]
    assert query["bool"]["filter"][0]["term"]["user_id"] == "__shared__"
    assert query["bool"]["minimum_should_match"] == 1


@pytest.mark.asyncio
async def test_search_all_sources_without_shared_returns_empty(adapter):
    inst, mock_client = adapter
    results = await inst.search_all_sources(
        user_id="any",
        sources=[ClothingSource.CLOSET],
        query="shirt",
    )
    assert results == []
    mock_client.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_empty_query_uses_filter_only(adapter):
    inst, mock_client = adapter
    mock_client.search.return_value = _make_es_response([])
    await inst.search_by_source(
        user_id="u", source=ClothingSource.SHARED_CLOSET, query="", limit=10
    )
    call_kwargs = mock_client.search.call_args.kwargs
    query = call_kwargs["query"]
    # Must still filter to __shared__
    assert query["bool"]["filter"][0]["term"]["user_id"] == "__shared__"
    # No should clause for empty query
    assert "should" not in query["bool"]


@pytest.mark.asyncio
async def test_search_fails_soft_on_es_error(adapter):
    inst, mock_client = adapter
    mock_client.search.side_effect = Exception("ES is down")
    results = await inst.search_by_source(
        user_id="u", source=ClothingSource.SHARED_CLOSET, query="shirt"
    )
    assert results == []


@pytest.mark.asyncio
async def test_image_url_fallback_when_no_imageUrl(adapter):
    """Adapter signs the R2 key when ES doc has no imageUrl field."""
    inst, mock_client = adapter
    hit = {
        "_id": "item-003",
        "_source": {
            "user_id": "__shared__",
            "tags": ["pants"],
            "category": "Pants",
            # No imageUrl field
        },
    }
    mock_client.search.return_value = _make_es_response([hit])
    results = await inst.search_by_source(
        user_id="u", source=ClothingSource.SHARED_CLOSET, query="pants"
    )
    assert results[0].image_url == "https://images.example.test/__shared__/closet/item-003.jpg"
