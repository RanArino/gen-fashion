from typing import List
from app.ports import EmbeddingSearchPort
from app.domain.styling import CandidateItem


class ElasticsearchEmbeddingRepository(EmbeddingSearchPort):
    """Elasticsearch adapter for embedding search (M2-9)."""

    async def search_similar(
        self, user_id: str, embedding_vector: List[float], limit: int = 10
    ) -> List[CandidateItem]:
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    async def index_item(self, item_id: str, user_id: str, embedding: List[float]) -> None:
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    async def delete_item(self, item_id: str, user_id: str) -> None:
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")
