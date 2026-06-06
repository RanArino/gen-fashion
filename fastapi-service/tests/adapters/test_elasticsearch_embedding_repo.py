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
            embedding=None,
        )
        await repo.delete_item("test-item", "user-123")
    finally:
        await repo._client.close()
