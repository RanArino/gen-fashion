from abc import ABC, abstractmethod


class SharedClosetGalleryPort(ABC):
    @abstractmethod
    async def list_closets(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def list_items(self, closet_id: str) -> list[dict]:
        raise NotImplementedError
