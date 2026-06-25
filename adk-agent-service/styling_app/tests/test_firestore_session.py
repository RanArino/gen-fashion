import pytest

from styling_app.adapters.firestore_session import FirestoreSessionRepository


class _FakeDoc:
    def __init__(self, store):
        self._store = store

    async def set(self, data, merge=False):
        self._store.append(data)


class _FakeCollection:
    def __init__(self, store):
        self._store = store

    def document(self, _doc_id):
        return _FakeDoc(self._store)


class _FakeClient:
    def __init__(self):
        self.writes = []

    def collection(self, _name):
        return _FakeCollection(self.writes)


def _statuses(client):
    return [w["status"] for w in client.writes if "status" in w]


@pytest.mark.asyncio
async def test_update_status_advances_and_dedupes():
    client = _FakeClient()
    repo = FirestoreSessionRepository(client=client)

    await repo.update_status("s1", "SEARCHING")
    await repo.update_status("s1", "SEARCHING")  # duplicate -> skipped
    await repo.update_status("s1", "PROPOSING")
    await repo.update_status("s1", "GENERATING")

    assert _statuses(client) == ["SEARCHING", "PROPOSING", "GENERATING"]


@pytest.mark.asyncio
async def test_update_status_never_regresses():
    client = _FakeClient()
    repo = FirestoreSessionRepository(client=client)

    await repo.update_status("s1", "GENERATING")
    await repo.update_status("s1", "SEARCHING")  # out-of-order -> ignored

    assert _statuses(client) == ["GENERATING"]


@pytest.mark.asyncio
async def test_status_locked_after_completion():
    client = _FakeClient()
    repo = FirestoreSessionRepository(client=client)

    await repo.update_status("s1", "SEARCHING")
    await repo.write_style_result("s1", {"coordinateImageUrl": "http://x"})
    await repo.update_status("s1", "GENERATING")  # post-completion -> ignored

    assert _statuses(client) == ["SEARCHING", "COMPLETED"]
