from app.ports import SharedClosetGalleryPort


class SharedClosetGalleryUseCase:
    """Read-only shared closet gallery facade."""

    def __init__(self, adapter: SharedClosetGalleryPort):
        self.adapter = adapter

    async def list_closets(self) -> list[dict]:
        return await self.adapter.list_closets()

    async def list_items(self, closet_id: str) -> list[dict]:
        return await self.adapter.list_items(closet_id)
