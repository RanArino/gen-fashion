import pytest
import asyncio
from app.adapters.local_task_queue import LocalHttpTaskQueueAdapter
from app.config import get_settings


class FakeResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text
        self.is_error = status_code >= 400


class FakeAsyncClient:
    response = FakeResponse()
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json, headers=None):
        self.calls.append((url, json, headers or {}))
        return self.response


@pytest.fixture(autouse=True)
def local_base_url(monkeypatch):
    # The worker route (/internal/tasks/process-upload) lives in fastapi-service,
    # so the local queue builds its URL from FASTAPI_INTERNAL_BASE_URL. Pin it so
    # the assertion is independent of the ambient container env.
    monkeypatch.setenv("ADK_INTERNAL_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FASTAPI_INTERNAL_BASE_URL", "http://localhost:8000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_local_task_queue_returns_task_id_when_handler_succeeds(monkeypatch):
    monkeypatch.delenv("INTERNAL_TASK_SECRET", raising=False)
    get_settings.cache_clear()
    FakeAsyncClient.response = FakeResponse()
    FakeAsyncClient.calls = []
    monkeypatch.setattr("app.adapters.local_task_queue.httpx.AsyncClient", FakeAsyncClient)

    task_id = await LocalHttpTaskQueueAdapter().enqueue_task(
        "embed-local",
        "/internal/tasks/process-upload",
        {"userId": "user-123", "item_id": "item-123"},
    )

    assert task_id
    await asyncio.sleep(0)
    assert FakeAsyncClient.calls == [
        (
            "http://localhost:8000/internal/tasks/process-upload",
            {"userId": "user-123", "item_id": "item-123"},
            {},
        )
    ]


@pytest.mark.asyncio
async def test_local_task_queue_sends_internal_secret_header_when_configured(monkeypatch):
    monkeypatch.setenv("INTERNAL_TASK_SECRET", "s3cret")
    get_settings.cache_clear()
    FakeAsyncClient.response = FakeResponse()
    FakeAsyncClient.calls = []
    monkeypatch.setattr("app.adapters.local_task_queue.httpx.AsyncClient", FakeAsyncClient)

    await LocalHttpTaskQueueAdapter().enqueue_task(
        "embed-local",
        "/internal/tasks/process-upload",
        {"userId": "user-123", "item_id": "item-123"},
    )

    await asyncio.sleep(0)
    assert FakeAsyncClient.calls[0][2] == {"X-Internal-Secret": "s3cret"}


@pytest.mark.asyncio
async def test_local_task_queue_does_not_fail_enqueue_when_handler_fails(monkeypatch):
    FakeAsyncClient.response = FakeResponse(status_code=500, text="analysis failed")
    FakeAsyncClient.calls = []
    monkeypatch.setattr("app.adapters.local_task_queue.httpx.AsyncClient", FakeAsyncClient)

    task_id = await LocalHttpTaskQueueAdapter().enqueue_task(
        "embed-local",
        "/internal/tasks/process-upload",
        {"userId": "user-123", "item_id": "item-123"},
    )

    assert task_id
    await asyncio.sleep(0)
    assert FakeAsyncClient.calls
