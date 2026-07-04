import pytest
from uuid import uuid4
from datetime import datetime
from app.domain.closet import (
    ClosetOwnershipStatus,
    ClothingItem,
    ClothingItemId,
    ClothingItemStatus,
    ClothingTag,
)


def test_create_clothing_item():
    """Test creating a valid clothing item."""
    item_id = ClothingItemId(uuid4())
    user_id = "user-123"
    image_url = "https://example.com/image.jpg"

    item = ClothingItem(
        id=item_id,
        user_id=user_id,
        image_url=image_url,
        tags=[],
    )

    assert item.id == item_id
    assert item.user_id == user_id
    assert item.image_url == image_url
    assert item.embedding is None


def test_add_tag_to_clothing_item():
    """Test adding tags to a clothing item."""
    item = ClothingItem(
        id=ClothingItemId(uuid4()),
        user_id="user-123",
        image_url="https://example.com/image.jpg",
        tags=[],
    )

    tag = ClothingTag(name="color", value="blue")
    item.add_tag(tag)

    assert tag in item.tags


def test_clothing_item_invalid_user_id():
    """Test that empty user_id raises error."""
    with pytest.raises(ValueError, match="user_id must not be empty"):
        ClothingItem(
            id=ClothingItemId(uuid4()),
            user_id="",
            image_url="https://example.com/image.jpg",
            tags=[],
        )


def test_clothing_item_invalid_image_url():
    """Test that empty image_url raises error."""
    with pytest.raises(ValueError, match="image_url must not be empty"):
        ClothingItem(
            id=ClothingItemId(uuid4()),
            user_id="user-123",
            image_url="",
            tags=[],
        )


def test_clothing_item_defaults_to_owned():
    item = ClothingItem(
        id=ClothingItemId(uuid4()),
        user_id="user-123",
        image_url="https://example.com/image.jpg",
        tags=[],
    )

    assert item.ownership_status == ClosetOwnershipStatus.OWNED
    assert item.origin is None


def test_ownership_status_transitions_keep_analysis_status():
    item = ClothingItem(
        id=ClothingItemId(uuid4()),
        user_id="user-123",
        image_url="https://example.com/image.jpg",
        tags=[],
        status=ClothingItemStatus.READY,
        ownership_status=ClosetOwnershipStatus.INTERESTING,
        origin="RAKUTEN",
    )

    item.set_ownership_status(ClosetOwnershipStatus.OWNED)
    assert item.ownership_status == ClosetOwnershipStatus.OWNED

    item.set_ownership_status(ClosetOwnershipStatus.INTERESTING)
    assert item.ownership_status == ClosetOwnershipStatus.INTERESTING
    assert item.status == ClothingItemStatus.READY
