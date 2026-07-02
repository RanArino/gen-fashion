from datetime import datetime
from uuid import uuid4

import pytest
from google.cloud import firestore

from app.adapters.firestore_styling_repo import FirestoreStylingRepository
from app.domain.styling import ClothingSource, StyleSession, StyleSessionId, StyleSessionState, UserPreference


class FakeSnapshot:
    def __init__(self, doc_id, data, exists=True):
        self.id = doc_id
        self._data = data
        self.exists = exists

    def to_dict(self):
        return self._data


def test_session_document_mapping_round_trips_m5_fields():
    session_id = uuid4()
    now = datetime.utcnow()
    session = StyleSession(
        id=StyleSessionId(session_id),
        user_id="user-123",
        state=StyleSessionState.SEARCHING,
        clothing_source=ClothingSource.SHARED_CLOSET,
        shared_closet_id="adult-01",
        user_preference=UserPreference(
            occasion="work", color_preference="blue", gender="female", language="en"
        ),
        selected_items=[{"itemId": "item-1"}],
        proposed_candidates=[{"item_id": "item-2"}],
        created_at=now,
        updated_at=now,
        completed_at=now,
    )

    data = FirestoreStylingRepository._to_document(session)
    restored = FirestoreStylingRepository._from_snapshot(FakeSnapshot(str(session_id), data))

    assert data["status"] == "SEARCHING"
    assert data["source"] == "SHARED_CLOSET"
    assert data["userPreference"]["colorPreference"] == "blue"
    assert data["userPreference"]["gender"] == "female"
    assert data["userPreference"]["language"] == "en"
    assert restored.user_id == "user-123"
    assert restored.state == StyleSessionState.SEARCHING
    assert restored.clothing_source == ClothingSource.SHARED_CLOSET
    assert restored.shared_closet_id == "adult-01"
    assert restored.selected_items == [{"itemId": "item-1"}]
    assert restored.proposed_candidates == [{"item_id": "item-2"}]
    assert restored.user_preference.gender == "female"
    assert restored.user_preference.language == "en"
    assert restored.completed_at == now


class FakeQuery:
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.calls = []

    def where(self, field, operator, value):
        self.calls.append(("where", field, operator, value))
        return self

    def order_by(self, field, direction=None):
        self.calls.append(("order_by", field, direction))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    async def stream(self):
        for snapshot in self.snapshots:
            yield snapshot


class FakeClient:
    def __init__(self, query):
        self.query = query

    def collection(self, name):
        assert name == "sessions"
        return self.query


@pytest.mark.asyncio
async def test_list_completed_firestore_query():
    session_id = uuid4()
    query = FakeQuery(
        [
            FakeSnapshot(
                str(session_id),
                {
                    "userId": "user-123",
                    "status": "COMPLETED",
                    "source": "SHARED_CLOSET",
                    "completedAt": datetime(2026, 6, 24, 10, 32),
                },
            )
        ]
    )
    repo = FirestoreStylingRepository.__new__(FirestoreStylingRepository)
    repo._client = FakeClient(query)

    sessions = await repo.list_completed("user-123", limit=10)

    assert len(sessions) == 1
    assert sessions[0].id == StyleSessionId(session_id)
    assert query.calls == [
        ("where", "userId", "==", "user-123"),
        ("where", "status", "==", "COMPLETED"),
        ("order_by", "completedAt", firestore.Query.DESCENDING),
        ("limit", 10),
    ]
