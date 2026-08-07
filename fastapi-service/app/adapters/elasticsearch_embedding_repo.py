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
        if settings.elasticsearch_ca_certs:
            kwargs["ca_certs"] = settings.elasticsearch_ca_certs
        if settings.elasticsearch_ssl_assert_fingerprint:
            kwargs["ssl_assert_fingerprint"] = settings.elasticsearch_ssl_assert_fingerprint
        if settings.elasticsearch_api_key:
            kwargs["api_key"] = settings.elasticsearch_api_key
        self._client = AsyncElasticsearch(**kwargs)
        self._index = settings.clothing_items_index
        self._dims = settings.embedding_dimensions

    async def ensure_index(self) -> None:
        exists = await self._client.indices.exists(index=self._index)
        if exists:
            # Additive mapping update: a new keyword property does not
            # require recreating the index, and applying it to an index that
            # already has it is a no-op. Without this, intentTags falls to
            # dynamic `text` mapping on every pre-existing index and the
            # exact-term boost clause (MR-6) matches nothing — the same
            # failure mode recorded for closetId in
            # docs/architecture-overview.md §8 item 4.
            await self._client.indices.put_mapping(
                index=self._index,
                properties={"intentTags": {"type": "keyword"}},
            )
            return
        await self._client.indices.create(
            index=self._index,
            mappings={
                "properties": {
                    "item_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "is_shared": {"type": "boolean"},
                    # Shared-closet (M3 seed) fields: kept as keyword so exact
                    # term filters work (e.g. closetId="adult-01"). Without this
                    # they fall to dynamic text mapping and term filters miss.
                    "closetId": {"type": "keyword"},
                    "closetKind": {"type": "keyword"},
                    "imageUrl": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "colors": {"type": "keyword"},
                    "season": {"type": "keyword"},
                    "gender": {"type": "keyword"},
                    # MK ownership/origin classification for imported suggestions.
                    "ownershipStatus": {"type": "keyword"},
                    "origin": {"type": "keyword"},
                    "externalItemId": {"type": "keyword"},
                    "externalUrl": {"type": "keyword"},
                    # MR intent vocabulary (see domain/shared/affective.py).
                    "intentTags": {"type": "keyword"},
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
        gender: Optional[str] = None,
        ownership_status: Optional[str] = None,
        origin: Optional[str] = None,
        external_item_id: Optional[str] = None,
        external_url: Optional[str] = None,
        intent_tags: Optional[List[str]] = None,
    ) -> None:
        document = {
            "item_id": item_id,
            "user_id": user_id,
            "is_shared": is_shared,
            "tags": tags,
            "category": category,
            "colors": colors,
            "season": season,
            "gender": gender,
            "intentTags": intent_tags or [],
        }
        if ownership_status is not None:
            document["ownershipStatus"] = ownership_status
        if origin is not None:
            document["origin"] = origin
        if external_item_id is not None:
            document["externalItemId"] = external_item_id
        if external_url is not None:
            document["externalUrl"] = external_url
        if embedding is not None:
            document["embedding"] = embedding
        await self._client.index(index=self._index, id=item_id, document=document)

    async def delete_item(self, item_id: str, user_id: str) -> None:
        try:
            await self._client.delete(index=self._index, id=item_id)
        except NotFoundError:
            return

    async def update_item_metadata(
        self,
        item_id: str,
        *,
        tags: List[str],
        category: Optional[str],
        colors: List[str],
        season: Optional[str],
        gender: Optional[str],
        ownership_status: Optional[str] = None,
        intent_tags: Optional[List[str]] = None,
    ) -> None:
        doc = {
            "tags": tags,
            "category": category,
            "colors": colors,
            "season": season,
            "gender": gender,
            "intentTags": intent_tags or [],
        }
        if ownership_status is not None:
            doc["ownershipStatus"] = ownership_status
        await self._client.update(
            index=self._index,
            id=item_id,
            doc=doc,
        )
