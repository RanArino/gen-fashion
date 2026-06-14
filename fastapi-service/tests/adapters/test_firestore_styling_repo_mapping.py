from datetime import datetime
from uuid import uuid4

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
        user_preference=UserPreference(occasion="work", color_preference="blue"),
        selected_items=[{"itemId": "item-1"}],
        created_at=now,
        updated_at=now,
    )

    data = FirestoreStylingRepository._to_document(session)
    restored = FirestoreStylingRepository._from_snapshot(FakeSnapshot(str(session_id), data))

    assert data["status"] == "SEARCHING"
    assert data["source"] == "SHARED_CLOSET"
    assert data["userPreference"]["colorPreference"] == "blue"
    assert restored.user_id == "user-123"
    assert restored.state == StyleSessionState.SEARCHING
    assert restored.clothing_source == ClothingSource.SHARED_CLOSET
    assert restored.shared_closet_id == "adult-01"
    assert restored.selected_items == [{"itemId": "item-1"}]
