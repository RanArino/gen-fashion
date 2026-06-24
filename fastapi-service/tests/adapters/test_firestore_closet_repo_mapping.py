from datetime import datetime
from uuid import UUID, uuid4
from app.adapters.firestore_closet_repo import FirestoreClosetRepository
from app.domain.closet import ClothingItem, ClothingItemId, ClothingItemStatus, ClothingTag


class FakeParent:
    def __init__(self, parent=None, id=None):
        self.parent = parent
        self.id = id


class FakeSnapshot:
    def __init__(self, item_id, data, user_id="user-123"):
        self.id = item_id
        self._data = data
        self.exists = True
        self.reference = FakeParent(FakeParent(id=user_id))

    def to_dict(self):
        return self._data


def test_firestore_document_mapping_round_trips_domain_shape():
    item_id = uuid4()
    created_at = datetime.utcnow()
    item = ClothingItem(
        id=ClothingItemId(item_id),
        user_id="user-123",
        image_url=f"user-123/closet/{item_id}.jpg",
        tags=[ClothingTag(name="tag", value="casual")],
        status=ClothingItemStatus.READY,
        category="shirt",
        colors=["blue"],
        season="spring",
        gender="common",
        created_at=created_at,
        updated_at=created_at,
    )

    document = FirestoreClosetRepository._to_document(item)
    restored = FirestoreClosetRepository._from_snapshot(FakeSnapshot(str(item_id), document))

    assert document["itemId"] == str(item_id)
    assert document["imageUrl"] == f"user-123/closet/{item_id}.jpg"
    assert document["status"] == "READY"
    assert document["embeddingId"] == str(item_id)
    assert document["tags"] == ["casual"]
    assert document["gender"] == "common"
    assert restored.id.value == item_id
    assert isinstance(restored.id.value, UUID)
    assert restored.status == ClothingItemStatus.READY
    assert restored.category == "shirt"
    assert restored.colors == ["blue"]
    assert restored.gender == "common"


def test_firestore_processing_document_omits_embedding_id():
    item_id = uuid4()
    item = ClothingItem(
        id=ClothingItemId(item_id),
        user_id="user-123",
        image_url=f"user-123/closet/{item_id}.jpg",
        tags=[],
        status=ClothingItemStatus.PROCESSING,
    )

    document = FirestoreClosetRepository._to_document(item)

    assert "embeddingId" not in document
