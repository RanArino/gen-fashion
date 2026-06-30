from typing import List

from elasticsearch import AsyncElasticsearch

from app.adapters.r2_image_storage import R2ImageStorage
from app.config import get_settings
from app.domain.styling import CandidateItem, ClothingSource
from google.cloud import firestore

from app.ports import ClothingSearchPort, ImageStoragePort, SharedClosetGalleryPort

_ATTRIBUTION = "Clothing Dataset (CC BY-SA 4.0)"


class SharedClosetSearchAdapter(ClothingSearchPort, SharedClosetGalleryPort):
    """Search adapter for the pre-seeded shared closet (M3-3).

    Queries the clothing_items ES index filtered to user_id:"__shared__",
    keyword-first with fail-soft kNN degradation for deployment-phase vectors.
    """

    def __init__(self, image_storage: ImageStoragePort | None = None) -> None:
        settings = get_settings()
        kwargs = {"hosts": [settings.resolved_elasticsearch_url], "verify_certs": False}
        if settings.elasticsearch_api_key:
            kwargs["api_key"] = settings.elasticsearch_api_key
        self._client = AsyncElasticsearch(**kwargs)
        self._index = settings.clothing_items_index
        self._image_storage = image_storage or R2ImageStorage()
        self._firestore = firestore.AsyncClient(
            project=settings.firestore_project_id,
            database=settings.firestore_database_id,
        )

    async def list_closets(self) -> list[dict]:
        closets = []
        async for snapshot in self._firestore.collection("shared_closets").stream():
            closets.append({"closetId": snapshot.id, **(snapshot.to_dict() or {})})
        return sorted(closets, key=lambda closet: closet["closetId"])

    async def list_items(self, closet_id: str) -> list[dict]:
        response = await self._client.search(
            index=self._index,
            size=100,
            query={
                "bool": {
                    "filter": [
                        {"term": {"user_id": "__shared__"}},
                        {"term": {"closetId": closet_id}},
                    ]
                }
            },
        )
        items = []
        for hit in response["hits"]["hits"]:
            source = hit.get("_source", {})
            image_path = source.get("imageUrl") or f"__shared__/closet/{hit['_id']}.jpg"
            items.append(
                {
                    "itemId": hit["_id"],
                    "imageUrl": await self._image_storage.get_download_url(image_path),
                    "category": source.get("category"),
                    "colors": source.get("colors", []),
                    "season": source.get("season"),
                    "tags": source.get("tags", []),
                    "gender": source.get("gender", "common"),
                    "attribution": _ATTRIBUTION,
                }
            )
        return items

    async def search_by_source(
        self, user_id: str, source: ClothingSource, query: str, limit: int = 10
    ) -> List[CandidateItem]:
        if source != ClothingSource.SHARED_CLOSET:
            raise ValueError(f"Unexpected source: {source}")
        return await self._search_shared(query, limit)

    async def search_all_sources(
        self, user_id: str, sources: List[ClothingSource], query: str, limit: int = 10
    ) -> List[CandidateItem]:
        if ClothingSource.SHARED_CLOSET not in sources:
            return []
        return await self._search_shared(query, limit)

    async def _search_shared(self, query: str, limit: int) -> List[CandidateItem]:
        shared_filter = {"term": {"user_id": "__shared__"}}

        if query:
            es_query = {
                "bool": {
                    "filter": [shared_filter],
                    "should": [
                        {"match": {"tags": query}},
                        {"match": {"category": query}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        else:
            es_query = {"bool": {"filter": [shared_filter]}}

        try:
            response = await self._client.search(
                index=self._index,
                size=limit,
                query=es_query,
            )
        except Exception:
            # Fail-soft: ES unavailable → return empty list rather than 500
            return []

        results: list[CandidateItem] = []
        for hit in response["hits"]["hits"]:
            source = hit.get("_source", {})
            image_path = source.get("imageUrl") or f"__shared__/closet/{hit['_id']}.jpg"
            image_url = await self._image_storage.get_download_url(image_path)
            results.append(
                CandidateItem(
                    item_id=hit["_id"],
                    source=ClothingSource.SHARED_CLOSET,
                    image_url=image_url,
                    tags=source.get("tags", []),
                    attribution=_ATTRIBUTION,
                )
            )
        return results
