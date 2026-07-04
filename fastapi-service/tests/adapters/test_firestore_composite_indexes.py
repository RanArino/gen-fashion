"""Guards against the class of bug behind the 2026-07-04 outage: a Firestore
query needed a composite index that was never declared in
firestore.indexes.json, so every call failed in production with
FailedPrecondition (the emulator does not enforce composite indexes, so this
went undetected until it hit prod). Each query method below is replayed
against a call-capturing fake, the required index is derived from the actual
calls made, and checked against the declared indexes -- so a query change
that isn't matched by an index update fails this test before merge.
"""
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.adapters.firestore_styling_repo import FirestoreStylingRepository
from tests.adapters._firestore_fakes import FakeClient, FakeQuery

INDEXES_FILE = Path(__file__).resolve().parents[3] / "firestore.indexes.json"


def _required_index(collection_group: str, calls: list[tuple]) -> tuple[str, frozenset, tuple]:
    where_calls = [call for call in calls if call[0] == "where"]
    order_by_calls = [call for call in calls if call[0] == "order_by"]

    equality_fields = frozenset(field for _, field, op, _ in where_calls if op == "==")
    order_by = [(field, direction) for _, field, direction in order_by_calls]
    if order_by:
        trailing = tuple(order_by)
    else:
        inequality_fields = [field for _, field, op, _ in where_calls if op != "=="]
        trailing = tuple((field, "ASCENDING") for field in inequality_fields)
    return collection_group, equality_fields, trailing


def _index_satisfies(index_fields: list[dict], spec: tuple[str, frozenset, tuple]) -> bool:
    _, equality_fields, trailing = spec
    fields = [f for f in index_fields if f["fieldPath"] != "__name__"]
    n = len(trailing)
    tail = tuple((f["fieldPath"], f["order"]) for f in fields[len(fields) - n :]) if n else ()
    if tail != trailing:
        return False
    head = frozenset(f["fieldPath"] for f in fields[: len(fields) - n])
    return head == equality_fields


def _assert_index_declared(spec: tuple[str, frozenset, tuple]) -> None:
    collection_group = spec[0]
    declared = json.loads(INDEXES_FILE.read_text())["indexes"]
    candidates = [idx for idx in declared if idx["collectionGroup"] == collection_group]
    assert any(_index_satisfies(idx["fields"], spec) for idx in candidates), (
        f"No composite index in {INDEXES_FILE} satisfies query on "
        f"'{collection_group}' requiring equality fields {set(spec[1])} "
        f"followed by {spec[2]}. Add one to firestore.indexes.json."
    )


@pytest.mark.asyncio
async def test_list_completed_query_has_matching_index():
    query = FakeQuery([])
    repo = FirestoreStylingRepository.__new__(FirestoreStylingRepository)
    repo._client = FakeClient(query)

    await repo.list_completed("user-123", limit=10)

    _assert_index_declared(_required_index("sessions", query.calls))


@pytest.mark.asyncio
async def test_count_completed_today_query_has_matching_index():
    query = FakeQuery([])
    repo = FirestoreStylingRepository.__new__(FirestoreStylingRepository)
    repo._client = FakeClient(query)

    await repo.count_completed_today("user-123", datetime(2026, 7, 4, 0, 0))

    _assert_index_declared(_required_index("sessions", query.calls))
