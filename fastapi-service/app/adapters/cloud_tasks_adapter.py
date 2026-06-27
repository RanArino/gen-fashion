from typing import Dict, Any
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from datetime import datetime, timedelta
import json
from app.ports import TaskQueuePort
from app.config import get_settings


class CloudTasksAdapter(TaskQueuePort):
    """Google Cloud Tasks adapter for async job queueing (M2-10)."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = tasks_v2.CloudTasksAsyncClient()

    async def enqueue_task(
        self, queue_name: str, handler_path: str, payload: Dict[str, Any], delay_seconds: int = 0
    ) -> str:
        queue = queue_name or self._settings.cloud_tasks_queue_embed
        if not queue:
            raise ValueError("queue_name or CLOUD_TASKS_QUEUE_EMBED is required")
        parent = self._client.queue_path(
            self._settings.project_id,
            self._settings.cloud_tasks_location,
            queue,
        )
        # The process-upload worker lives in fastapi-service, not the ADK service.
        # Use FASTAPI_INTERNAL_BASE_URL when set; fall back to adk_internal_base_url
        # only for local dev where both routes are on the same host.
        worker_base = (
            self._settings.fastapi_internal_base_url or self._settings.adk_internal_base_url
        )
        url = f"{worker_base.rstrip('/')}{handler_path}"
        headers = {"Content-Type": "application/json"}
        # Defense-in-depth: shared secret is always sent alongside the OIDC token.
        if self._settings.internal_task_secret:
            headers["X-Internal-Secret"] = self._settings.internal_task_secret
        http_request = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": headers,
            "body": json.dumps(payload).encode("utf-8"),
        }
        # Production OIDC hardening: attach a Cloud Tasks OIDC token so the
        # fastapi worker can cryptographically verify the caller (MD-8).
        if self._settings.internal_invoker_sa and self._settings.fastapi_internal_base_url:
            http_request["oidc_token"] = {
                "service_account_email": self._settings.internal_invoker_sa,
                "audience": self._settings.fastapi_internal_base_url.rstrip("/"),
            }
        task = {"http_request": http_request}
        if delay_seconds > 0:
            schedule_time = timestamp_pb2.Timestamp()
            schedule_time.FromDatetime(datetime.utcnow() + timedelta(seconds=delay_seconds))
            task["schedule_time"] = schedule_time
        response = await self._client.create_task(parent=parent, task=task)
        return response.name

    async def get_task_status(self, queue_name: str, task_id: str) -> str:
        return "UNKNOWN"
