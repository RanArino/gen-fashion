from abc import ABC, abstractmethod
from typing import List, Optional
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
        """Index a clothing item document and optional embedding."""
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    @abstractmethod
    async def delete_item(self, item_id: str, user_id: str) -> None:
        """Delete an item from the embedding index."""
        raise NotImplementedError("Implement in M2-9: Elasticsearch adapter")

    @abstractmethod
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
        """Partially update searchable metadata without replacing the vector."""
        raise NotImplementedError
