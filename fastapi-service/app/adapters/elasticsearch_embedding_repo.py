from typing import List, Optional
from elasticsearch import AsyncElasticsearch, NotFoundError
from app.config import get_settings
from app.ports import EmbeddingSearchPort
from app.domain.styling import CandidateItem, ClothingSource


class ElasticsearchEmbeddingRepository(EmbeddingSearchPort):
    """Elasticsearch adapter for embedding search (M2-9)."""

    def __init__(self) -> None:
        settings = get_settings()
        kwargs = {"hosts": [settings.resolved_elasticsearch_url]}
        if settings.elasticsearch_api_key:
            kwargs["api_key"] = settings.elasticsearch_api_key
        self._client = AsyncElasticsearch(**kwargs)
        self._index = settings.clothing_items_index
        self._dims = settings.embedding_dimensions

    async def ensure_index(self) -> None:
        exists = await self._client.indices.exists(index=self._index)
        if exists:
            return
        await self._client.indices.create(
            index=self._index,
            mappings={
                "properties": {
                    "item_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "is_shared": {"type": "boolean"},
                    "tags": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "colors": {"type": "keyword"},
                    "season": {"type": "keyword"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self._dims,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )

    async def search_similar(
        self, user_id: str, embedding_vector: List[float], limit: int = 10
    ) -> List[CandidateItem]:
        response = await self._client.search(
            index=self._index,
            size=limit,
            query={"term": {"user_id": user_id}},
        )
        return [
            CandidateItem(
                item_id=hit["_id"],
                source=ClothingSource.CLOSET,
                image_url="",
                tags=hit.get("_source", {}).get("tags", []),
            )
            for hit in response["hits"]["hits"]
        ]

    async def index_item(
        self,
        item_id: str,
        user_id: str,
        *,
        is_shared: bool,
        tags: List[str],
        category: Optional[str],
        colors: List[str],
        season: Optional[str],
        embedding: Optional[List[float]],
    ) -> None:
        document = {
            "item_id": item_id,
            "user_id": user_id,
            "is_shared": is_shared,
            "tags": tags,
            "category": category,
            "colors": colors,
            "season": season,
        }
        if embedding is not None:
            document["embedding"] = embedding
        await self._client.index(index=self._index, id=item_id, document=document)

    async def delete_item(self, item_id: str, user_id: str) -> None:
        try:
            await self._client.delete(index=self._index, id=item_id)
        except NotFoundError:
            return
