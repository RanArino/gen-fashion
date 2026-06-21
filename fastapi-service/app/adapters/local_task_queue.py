from typing import Any, Dict
import asyncio
import logging
from uuid import uuid4
import httpx
from app.config import get_settings
from app.ports import TaskQueuePort


logger = logging.getLogger(__name__)


class LocalHttpTaskQueueAdapter(TaskQueuePort):
    """Local task queue adapter that calls the internal worker endpoint directly."""

    async def enqueue_task(
        self, queue_name: str, handler_path: str, payload: Dict[str, Any], delay_seconds: int = 0
    ) -> str:
        task_id = str(uuid4())
        asyncio.create_task(self._dispatch(task_id, handler_path, payload))
        return task_id

    async def _dispatch(self, task_id: str, handler_path: str, payload: Dict[str, Any]) -> None:
        settings = get_settings()
        base_url = settings.fastapi_internal_base_url or settings.adk_internal_base_url
        url = f"{base_url.rstrip('/')}{handler_path}"
        headers: Dict[str, str] = {}
        if settings.internal_task_secret:
            headers["X-Internal-Secret"] = settings.internal_task_secret
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(url, json=payload, headers=headers)
        except Exception:
            logger.exception("Local task %s handler %s request failed", task_id, handler_path)
            return
        if response.is_error:
            logger.warning(
                "Local task %s handler %s returned HTTP %s: %s",
                task_id,
                handler_path,
                response.status_code,
                response.text,
            )

    async def get_task_status(self, queue_name: str, task_id: str) -> str:
        return "UNKNOWN"
