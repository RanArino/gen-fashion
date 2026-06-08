from app.ports import ClosetRepositoryPort, TaskQueuePort


class RegisterClothingItemUseCase:
    """Use case for registering an uploaded item (M2-4)."""

    def __init__(self, closet_repo: ClosetRepositoryPort, task_queue: TaskQueuePort):
        self.closet_repo = closet_repo
        self.task_queue = task_queue

    async def execute(self, user_id: str, item_id: str, image_url: str) -> None:
        raise NotImplementedError("Implement in M2-4: Register clothing item")
