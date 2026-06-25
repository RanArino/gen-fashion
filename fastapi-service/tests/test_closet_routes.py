from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import verify_firebase_token
from app.dependencies import (
    get_delete_closet_item_use_case,
    get_download_url_use_case,
    get_register_clothing_item_use_case,
    get_upload_url_use_case,
)
from app.domain.closet import ClosetItemNotFound, MaxClosetItemsExceeded
from app.main import app


class UploadUseCase:
    def __init__(self, error=None):
        self.error = error

    async def execute(self, user_id, item_id):
        if self.error:
            raise self.error
        return f"http://storage/{user_id}/closet/{item_id}.jpg"


class RegisterUseCase:
    async def execute(self, user_id, item_id):
        return {"item_id": item_id, "status": "PROCESSING"}


class DeleteUseCase:
    def __init__(self, error=None):
        self.error = error

    async def execute(self, user_id, item_id):
        if self.error:
            raise self.error


def reset_overrides():
    app.dependency_overrides = {}


def test_upload_url_requires_bearer_token():
    reset_overrides()
    client = TestClient(app)

    response = client.get(f"/closet/upload-url?item_id={uuid4()}")

    assert response.status_code == 401


def test_upload_url_returns_signed_url_with_auth_override():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_upload_url_use_case] = lambda: UploadUseCase()
    client = TestClient(app)
    item_id = str(uuid4())

    response = client.get(f"/closet/upload-url?item_id={item_id}")

    assert response.status_code == 200
    assert response.json() == {
        "upload_url": f"http://storage/user-123/closet/{item_id}.jpg",
        "item_id": item_id,
    }
    reset_overrides()


def test_upload_url_maps_cap_to_429():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_upload_url_use_case] = lambda: UploadUseCase(
        MaxClosetItemsExceeded("cap")
    )
    client = TestClient(app)

    response = client.get(f"/closet/upload-url?item_id={uuid4()}")

    assert response.status_code == 429
    reset_overrides()


class DownloadUseCase:
    async def execute(self, user_id, item_id):
        return f"http://storage/{user_id}/closet/{item_id}.jpg?sig=abc"


def test_download_url_requires_bearer_token():
    reset_overrides()
    client = TestClient(app)

    response = client.get(f"/closet/items/{uuid4()}/download-url")

    assert response.status_code == 401


def test_download_url_returns_signed_url_with_auth_override():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_download_url_use_case] = lambda: DownloadUseCase()
    client = TestClient(app)
    item_id = str(uuid4())

    response = client.get(f"/closet/items/{item_id}/download-url")

    assert response.status_code == 200
    assert response.json() == {
        "download_url": f"http://storage/user-123/closet/{item_id}.jpg?sig=abc",
    }
    reset_overrides()


def test_register_route_returns_processing():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_register_clothing_item_use_case] = lambda: RegisterUseCase()
    client = TestClient(app)
    item_id = str(uuid4())

    response = client.post(f"/closet/items/{item_id}/complete")

    assert response.status_code == 200
    assert response.json() == {"item_id": item_id, "status": "PROCESSING"}
    reset_overrides()


def test_delete_route_maps_success_and_missing_item():
    reset_overrides()
    app.dependency_overrides[verify_firebase_token] = lambda: "user-123"
    app.dependency_overrides[get_delete_closet_item_use_case] = lambda: DeleteUseCase()
    client = TestClient(app)

    assert client.delete(f"/closet/items/{uuid4()}").status_code == 204

    app.dependency_overrides[get_delete_closet_item_use_case] = lambda: DeleteUseCase(
        ClosetItemNotFound("missing")
    )
    assert client.delete(f"/closet/items/{uuid4()}").status_code == 404
    reset_overrides()
