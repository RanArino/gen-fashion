from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.adapters.elasticsearch_embedding_repo import ElasticsearchEmbeddingRepository
from app.config import get_settings


@pytest.mark.asyncio
async def test_elasticsearch_embedding_repo_index_lifecycle(monkeypatch):
    elasticsearch_url = get_settings().resolved_elasticsearch_url
    async with httpx.AsyncClient() as client:
        try:
            await client.get(elasticsearch_url, timeout=1.0)
        except Exception:
            pytest.skip(f"Elasticsearch is not reachable at {elasticsearch_url}")

    monkeypatch.setenv("CLOTHING_ITEMS_INDEX", "clothing_items_test")
    repo = ElasticsearchEmbeddingRepository()

    try:
        await repo.ensure_index()
        await repo.index_item(
            item_id="test-item",
            user_id="user-123",
            is_shared=False,
            tags=["casual"],
            category="shirt",
            colors=["blue"],
            season="spring",
            embedding=[0.1] * repo._dims,
        )
        await repo.update_item_metadata(
            "test-item",
            tags=["formal"],
            category="shirt",
            colors=["navy"],
            season="autumn",
            gender="common",
        )
        stored = await repo._client.get(index=repo._index, id="test-item")
        assert stored["_source"]["tags"] == ["formal"]
        assert stored["_source"]["embedding"] == [0.1] * repo._dims
        await repo.delete_item("test-item", "user-123")
    finally:
        await repo._client.close()


@pytest.mark.asyncio
async def test_ensure_index_issues_put_mapping_when_index_already_exists():
    """A4: an existing index must gain intentTags via put_mapping, not a no-op.

    Without this, intentTags falls to dynamic `text` mapping on every
    pre-existing index and the Milestone B boost clause silently matches
    nothing (see docs/architecture-overview.md §8 item 4 for the closetId
    precedent of this exact failure mode).
    """
    with patch("app.adapters.elasticsearch_embedding_repo.AsyncElasticsearch") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.indices.exists.return_value = True

        repo = ElasticsearchEmbeddingRepository()
        await repo.ensure_index()

        mock_client.indices.put_mapping.assert_awaited_once_with(
            index=repo._index,
            properties={"intentTags": {"type": "keyword"}},
        )
        mock_client.indices.create.assert_not_called()
