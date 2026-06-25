from uuid import UUID
from app.config import get_settings
from app.domain.closet import ClothingItem, ClothingItemId
from app.ports import ClosetRepositoryPort, TaskQueuePort


class RegisterClothingItemUseCase:
    """Use case for registering an uploaded item (M2-4)."""

    def __init__(self, closet_repo: ClosetRepositoryPort, task_queue: TaskQueuePort):
        self.closet_repo = closet_repo
        self.task_queue = task_queue

    async def execute(self, user_id: str, item_id: str) -> dict:
        image_path = f"{user_id}/closet/{item_id}.jpg"
        item = ClothingItem(
            id=ClothingItemId(UUID(item_id)),
            user_id=user_id,
            image_url=image_path,
            tags=[],
        )
        await self.closet_repo.create(item)
        settings = get_settings()
        await self.task_queue.enqueue_task(
            queue_name=settings.cloud_tasks_queue_embed or "embed-local",
            handler_path="/internal/tasks/process-upload",
            payload={"userId": user_id, "item_id": item_id},
        )
        return {"item_id": item_id, "status": item.status.value}
