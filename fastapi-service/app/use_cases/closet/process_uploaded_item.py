from app.ports import (
    ClosetRepositoryPort,
    EmbeddingSearchPort,
)


class ProcessUploadedClothingItemUseCase:
    """Use case for processing uploaded item (analysis + embedding) (M2-5)."""

    def __init__(self, closet_repo: ClosetRepositoryPort, embedding_search: EmbeddingSearchPort):
        self.closet_repo = closet_repo
        self.embedding_search = embedding_search

    async def execute(self, user_id: str, item_id: str, image_url: str) -> None:
        raise NotImplementedError("Implement in M2-5: Process uploaded item")
