from abc import ABC, abstractmethod
from typing import List
from app.domain.styling import CandidateItem


class EmbeddingSearchPort(ABC):
    """Port for dense vector search over image embeddings."""

    @abstractmethod
    async def search_similar(
        self, user_id: str, embedding_vector: List[float], limit: int = 10
    ) -> List[CandidateItem]:
        """Search for similar items by embedding vector (from uploaded image)."""
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    @abstractmethod
    async def index_item(self, item_id: str, user_id: str, embedding: List[float]) -> None:
        """Index a clothing item embedding."""
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    @abstractmethod
    async def delete_item(self, item_id: str, user_id: str) -> None:
        """Delete an item from the embedding index."""
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")
