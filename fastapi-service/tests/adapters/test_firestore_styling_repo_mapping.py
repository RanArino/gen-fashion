from datetime import datetime
from uuid import uuid4

import pytest
from google.cloud import firestore

from app.adapters.firestore_styling_repo import FirestoreStylingRepository
from app.domain.styling import (
    ClothingSource,
    CoordinationMode,
    StyleSession,
    StyleSessionId,
    StyleSessionState,
    UserPreference,
)
from tests.adapters._firestore_fakes import FakeClient, FakeQuery


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


def test_session_document_mapping_round_trips_assisted_fields():
    session_id = uuid4()
    anchors = [{"item_id": "item-1", "source": "CLOSET", "anchor": True}]
    session = StyleSession(
        id=StyleSessionId(session_id),
        user_id="user-123",
        state=StyleSessionState.SEARCHING,
        clothing_source=ClothingSource.CLOSET,
        coordination_mode=CoordinationMode.ASSISTED,
        anchor_items=anchors,
    )

    data = FirestoreStylingRepository._to_document(session)
    restored = FirestoreStylingRepository._from_snapshot(FakeSnapshot(str(session_id), data))

    assert data["coordinationMode"] == "ASSISTED"
    assert data["anchorItems"] == anchors
    assert restored.coordination_mode == CoordinationMode.ASSISTED
    assert restored.anchor_items == anchors


def test_session_document_without_mode_defaults_to_standard():
    session_id = uuid4()
    restored = FirestoreStylingRepository._from_snapshot(
        FakeSnapshot(
            str(session_id),
            {"userId": "user-123", "status": "SOURCE_SELECTING", "source": "UNSET"},
        )
    )

    assert restored.coordination_mode == CoordinationMode.STANDARD
    assert restored.anchor_items == []


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


@pytest.mark.asyncio
async def test_count_completed_today_firestore_query():
    query = FakeQuery([])
    repo = FirestoreStylingRepository.__new__(FirestoreStylingRepository)
    repo._client = FakeClient(query)
    since = datetime(2026, 7, 4, 0, 0)

    count = await repo.count_completed_today("user-123", since)

    assert count == 0
    assert query.calls[0] == ("where", "userId", "==", "user-123")
    assert query.calls[1] == ("where", "status", "==", "COMPLETED")
    assert query.calls[2] == ("where", "completedAt", ">=", since)
    assert query.calls[3][0] == "limit"
