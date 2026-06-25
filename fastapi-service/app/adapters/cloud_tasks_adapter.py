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
        url = f"{self._settings.adk_internal_base_url.rstrip('/')}{handler_path}"
        headers = {"Content-Type": "application/json"}
        # Defense-in-depth stopgap: the worker also accepts the shared secret.
        if self._settings.internal_task_secret:
            headers["X-Internal-Secret"] = self._settings.internal_task_secret
        http_request = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": headers,
            "body": json.dumps(payload).encode("utf-8"),
        }
        # TODO(deploy): BLOCKING security gate before any public deploy — set an
        # OIDC token so the worker can cryptographically verify the caller, and
        # set Cloud Run ingress=internal. Replace the shared-secret stopgap with:
        #   http_request["oidc_token"] = {
        #       "service_account_email": self._settings.internal_invoker_sa,
        #       "audience": self._settings.adk_internal_base_url,
        #   }
        # and verify the bearer in require_internal_secret. See M2 ExecPlan Decision Log.
        task = {"http_request": http_request}
        if delay_seconds > 0:
            schedule_time = timestamp_pb2.Timestamp()
            schedule_time.FromDatetime(datetime.utcnow() + timedelta(seconds=delay_seconds))
            task["schedule_time"] = schedule_time
        response = await self._client.create_task(parent=parent, task=task)
        return response.name

    async def get_task_status(self, queue_name: str, task_id: str) -> str:
        return "UNKNOWN"
