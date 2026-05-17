from app.ports import ClosetRepositoryPort, ImageStoragePort, EmbeddingSearchPort


class DeleteClosetItemUseCase:
    """Use case for deleting a closet item (M2-6)."""

    def __init__(
        self,
        closet_repo: ClosetRepositoryPort,
        image_storage: ImageStoragePort,
        embedding_search: EmbeddingSearchPort,
    ):
        self.closet_repo = closet_repo
        self.image_storage = image_storage
        self.embedding_search = embedding_search

    async def execute(self, user_id: str, item_id: str) -> None:
        raise NotImplementedError("Implement in M2-6: Delete closet item")
