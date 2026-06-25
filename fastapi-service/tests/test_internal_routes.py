import pytest
from fastapi.testclient import TestClient
from app.config import get_settings
from app.dependencies import get_process_uploaded_item_use_case
from app.main import app


class ProcessUseCase:
    def __init__(self):
        self.calls = []

    async def execute(self, user_id, item_id):
        self.calls.append((user_id, item_id))


def reset_overrides():
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def _configured_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_TASK_SECRET", "s3cret")
    get_settings.cache_clear()
    yield
    reset_overrides()
    get_settings.cache_clear()


def test_internal_route_rejects_missing_secret():
    reset_overrides()
    client = TestClient(app)

    response = client.post(
        "/internal/tasks/process-upload",
        json={"userId": "u", "item_id": "i"},
    )

    assert response.status_code == 403


def test_internal_route_rejects_wrong_secret():
    reset_overrides()
    client = TestClient(app)

    response = client.post(
        "/internal/tasks/process-upload",
        json={"userId": "u", "item_id": "i"},
        headers={"X-Internal-Secret": "nope"},
    )

    assert response.status_code == 403


def test_internal_route_accepts_valid_secret():
    reset_overrides()
    use_case = ProcessUseCase()
    app.dependency_overrides[get_process_uploaded_item_use_case] = lambda: use_case
    client = TestClient(app)

    response = client.post(
        "/internal/tasks/process-upload",
        json={"userId": "u", "item_id": "i"},
        headers={"X-Internal-Secret": "s3cret"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert use_case.calls == [("u", "i")]
    reset_overrides()


def test_internal_route_locked_when_secret_unset(monkeypatch):
    reset_overrides()
    monkeypatch.delenv("INTERNAL_TASK_SECRET", raising=False)
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.post(
        "/internal/tasks/process-upload",
        json={"userId": "u", "item_id": "i"},
        headers={"X-Internal-Secret": "anything"},
    )

    assert response.status_code == 503
