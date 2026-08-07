from datetime import datetime
from uuid import UUID, uuid4
from app.adapters.firestore_closet_repo import FirestoreClosetRepository
from app.domain.closet import (
    ClosetOwnershipStatus,
    ClothingItem,
    ClothingItemId,
    ClothingItemStatus,
    ClothingTag,
    IntentTag,
)


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


def test_firestore_document_without_ownership_status_defaults_to_owned():
    item_id = uuid4()
    data = {
        "userId": "user-123",
        "imageUrl": f"user-123/closet/{item_id}.jpg",
        "status": "READY",
    }

    restored = FirestoreClosetRepository._from_snapshot(FakeSnapshot(str(item_id), data))

    assert restored.ownership_status == ClosetOwnershipStatus.OWNED
    assert restored.origin is None


def test_firestore_interesting_rakuten_item_round_trips():
    item_id = uuid4()
    item = ClothingItem(
        id=ClothingItemId(item_id),
        user_id="user-123",
        image_url=f"user-123/closet/{item_id}.jpg",
        tags=[],
        status=ClothingItemStatus.READY,
        ownership_status=ClosetOwnershipStatus.INTERESTING,
        origin="RAKUTEN",
        external_item_id="rakuten:shop:1001",
        external_url="https://item.rakuten.co.jp/shop/1001",
        affiliate_url="https://hb.afl.rakuten.co.jp/xyz",
        price=2980.0,
        brand_or_shop="Shop Name",
    )

    document = FirestoreClosetRepository._to_document(item)
    restored = FirestoreClosetRepository._from_snapshot(FakeSnapshot(str(item_id), document))

    assert document["ownershipStatus"] == "INTERESTING"
    assert document["origin"] == "RAKUTEN"
    assert restored.ownership_status == ClosetOwnershipStatus.INTERESTING
    assert restored.external_item_id == "rakuten:shop:1001"
    assert restored.external_url == "https://item.rakuten.co.jp/shop/1001"
    assert restored.affiliate_url == "https://hb.afl.rakuten.co.jp/xyz"
    assert restored.price == 2980.0
    assert restored.brand_or_shop == "Shop Name"


def test_firestore_document_without_intent_tags_loads_as_empty():
    """A3: every pre-existing document lacks intentTags; this is the common
    case, not an edge case."""
    item_id = uuid4()
    data = {
        "userId": "user-123",
        "imageUrl": f"user-123/closet/{item_id}.jpg",
        "status": "READY",
    }

    restored = FirestoreClosetRepository._from_snapshot(FakeSnapshot(str(item_id), data))

    assert restored.intent_tags == []
    assert restored.intent_vocabulary_version is None


def test_firestore_document_round_trips_intent_tags():
    item_id = uuid4()
    item = ClothingItem(
        id=ClothingItemId(item_id),
        user_id="user-123",
        image_url=f"user-123/closet/{item_id}.jpg",
        tags=[],
        status=ClothingItemStatus.READY,
    )
    item.set_intent_tags([IntentTag.CONFIDENT, IntentTag.AT_EASE])

    document = FirestoreClosetRepository._to_document(item)
    restored = FirestoreClosetRepository._from_snapshot(FakeSnapshot(str(item_id), document))

    assert document["intentTags"] == ["CONFIDENT", "AT_EASE"]
    assert document["intentVocabularyVersion"] == 1
    assert restored.intent_tags == [IntentTag.CONFIDENT, IntentTag.AT_EASE]
    assert restored.intent_vocabulary_version == 1


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
