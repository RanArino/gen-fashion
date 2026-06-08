from typing import Dict, Any
from app.ports import TaskQueuePort


class CloudTasksAdapter(TaskQueuePort):
    """Google Cloud Tasks adapter for async job queueing (M2-10)."""

    async def enqueue_task(
        self, queue_name: str, handler_path: str, payload: Dict[str, Any], delay_seconds: int = 0
    ) -> str:
        raise NotImplementedError("Implement in M2-10: Cloud Tasks adapter")

    async def get_task_status(self, queue_name: str, task_id: str) -> str:
        raise NotImplementedError("Implement in M2-10: Cloud Tasks adapter")
