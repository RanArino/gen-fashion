import asyncio
from types import SimpleNamespace

import pytest

from app.adapters.cloud_tasks_adapter import CloudTasksAdapter
from app.config import get_settings


class FakeCloudTasksClient:
    calls = []

    def queue_path(self, project_id, location, queue):
        return f"projects/{project_id}/locations/{location}/queues/{queue}"

    def create_task(self, parent, task):
        self.calls.append((parent, task))
        return SimpleNamespace(name=f"{parent}/tasks/task-123")


@pytest.fixture(autouse=True)
def cloud_tasks_settings(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("CLOUD_TASKS_LOCATION", "asia-northeast1")
    monkeypatch.setenv("CLOUD_TASKS_QUEUE_EMBED", "embed")
    monkeypatch.setenv("FASTAPI_INTERNAL_BASE_URL", "https://fastapi-service.example.test")
    monkeypatch.delenv("INTERNAL_TASK_SECRET", raising=False)
    monkeypatch.delenv("INTERNAL_INVOKER_SA", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cloud_tasks_adapter_can_be_constructed_from_worker_thread(monkeypatch):
    FakeCloudTasksClient.calls = []
    monkeypatch.setattr(
        "app.adapters.cloud_tasks_adapter.tasks_v2.CloudTasksClient",
        FakeCloudTasksClient,
    )
    monkeypatch.setattr(
        "app.adapters.cloud_tasks_adapter.tasks_v2.CloudTasksAsyncClient",
        lambda: pytest.fail("CloudTasksAsyncClient requires an event loop in worker threads"),
    )

    adapter = await asyncio.to_thread(CloudTasksAdapter)
    task_name = await adapter.enqueue_task(
        queue_name="",
        handler_path="/internal/tasks/process-upload",
        payload={"userId": "user-123", "item_id": "item-123"},
    )

    assert task_name == (
        "projects/test-project/locations/asia-northeast1/queues/embed/tasks/task-123"
    )
    parent, task = FakeCloudTasksClient.calls[0]
    assert parent == "projects/test-project/locations/asia-northeast1/queues/embed"
    assert task["http_request"]["url"] == (
        "https://fastapi-service.example.test/internal/tasks/process-upload"
    )
    assert task["http_request"]["body"] == b'{"userId": "user-123", "item_id": "item-123"}'
