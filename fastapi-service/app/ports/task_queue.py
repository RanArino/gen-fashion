from abc import ABC, abstractmethod
from typing import Dict, Any


class TaskQueuePort(ABC):
    """Port for enqueuing async jobs (e.g., to Cloud Tasks)."""

    @abstractmethod
    async def enqueue_task(
        self, queue_name: str, handler_path: str, payload: Dict[str, Any], delay_seconds: int = 0
    ) -> str:
        """
        Enqueue a task to be processed asynchronously.
        Returns task ID.
        """
        raise NotImplementedError("Implement in M2-10: Cloud Tasks adapter")

    @abstractmethod
    async def get_task_status(self, queue_name: str, task_id: str) -> str:
        """Get the status of an enqueued task."""
        raise NotImplementedError("Implement in M2-10: Cloud Tasks adapter")
