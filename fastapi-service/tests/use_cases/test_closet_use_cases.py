from uuid import UUID, uuid4
import pytest
from app.config import get_settings
from app.domain.closet import (
    ClosetOwnershipStatus,
    ClothingItem,
    ClothingItemId,
    ClothingItemStatus,
)
from app.domain.closet.exceptions import ClosetItemNotFound, MaxClosetItemsExceeded
from app.domain.styling import StyleSession, StyleSessionId, StyleSessionNotFound
from app.domain.styling.state_machine import StyleSessionState
from app.ports import ClothingAnalysisResult
from app.use_cases.closet import (
    DeleteClosetItemUseCase,
    GetUploadUrlUseCase,
    ImportSuggestedClosetItemUseCase,
    ProcessUploadedClothingItemUseCase,
    RegisterClothingItemUseCase,
    UpdateClosetItemMetadataUseCase,
)


class FakeClosetRepo:
    def __init__(self):
        self.items = {}

    async def create(self, item):
        self.items[(item.user_id, str(item.id))] = item

    async def get_by_id(self, user_id, item_id):
        return self.items.get((user_id, str(item_id)))

    async def get_all_by_user(self, user_id):
        return [item for (uid, _), item in self.items.items() if uid == user_id]

    async def update(self, item):
        self.items[(item.user_id, str(item.id))] = item

    async def delete(self, user_id, item_id):
        self.items.pop((user_id, str(item_id)), None)

    async def count_by_user(self, user_id):
        return len(await self.get_all_by_user(user_id))


class FakeImageStorage:
    def __init__(self):
        self.bytes_by_path = {}
        self.deleted = []
        self.fail_delete = False

    async def get_signed_upload_url(self, user_id, item_id, expiration_seconds=900):
        return f"http://storage/{user_id}/closet/{item_id}.jpg?ttl={expiration_seconds}"

    async def get_download_url(self, image_path):
        return f"http://storage/{image_path}"

    async def delete_image(self, image_path):
        if self.fail_delete:
            raise RuntimeError("delete failed")
        self.deleted.append(image_path)

    async def verify_image_exists(self, image_path):
        return image_path in self.bytes_by_path

    async def get_image_bytes(self, image_path):
        return self.bytes_by_path[image_path]

    async def put_image_bytes(self, image_path, data, content_type="image/jpeg"):
        self.bytes_by_path[image_path] = data


class FakeEmbeddingSearch:
    def __init__(self):
        self.indexed = []
        self.deleted = []
        self.fail_delete = False

    async def search_similar(self, user_id, embedding_vector, limit=10):
        return []

    async def index_item(
        self, item_id, user_id, *, is_shared, tags, category, colors, season,
        embedding, gender=None, ownership_status=None, origin=None,
        external_item_id=None, external_url=None
    ):
        self.indexed.append(
            {
                "item_id": item_id,
                "user_id": user_id,
                "is_shared": is_shared,
                "tags": tags,
                "category": category,
                "colors": colors,
                "season": season,
                "embedding": embedding,
                "gender": gender,
                "ownership_status": ownership_status,
                "origin": origin,
                "external_item_id": external_item_id,
                "external_url": external_url,
            }
        )

    async def delete_item(self, item_id, user_id):
        if self.fail_delete:
            raise RuntimeError("delete failed")
        self.deleted.append((item_id, user_id))

    async def update_item_metadata(
        self, item_id, *, tags, category, colors, season, gender, ownership_status=None
    ):
        self.indexed.append(
            {
                "item_id": item_id,
                "tags": tags,
                "category": category,
                "colors": colors,
                "season": season,
                "gender": gender,
                "ownership_status": ownership_status,
            }
        )


class FakeTaskQueue:
    def __init__(self):
        self.tasks = []

    async def enqueue_task(self, queue_name, handler_path, payload, delay_seconds=0):
        self.tasks.append((queue_name, handler_path, payload, delay_seconds))
        return "task-1"

    async def get_task_status(self, queue_name, task_id):
        return "UNKNOWN"


class FakeGemini:
    def __init__(self, fail_analysis=False, fail_embedding=False):
        self.fail_analysis = fail_analysis
        self.fail_embedding = fail_embedding

    async def analyze(self, image_bytes):
        if self.fail_analysis:
            raise RuntimeError("analysis failed")
        return ClothingAnalysisResult(
            category="shirt",
            colors=["blue"],
            tags=["casual", "cotton"],
            season="spring",
            style="minimal",
        )

    async def embed_text(self, text):
        if self.fail_embedding:
            raise RuntimeError("embedding failed")
        return [0.1, 0.2, 0.3]


def closet_item(user_id="user-123", item_id=None):
    item_id = item_id or uuid4()
    return ClothingItem(
        id=ClothingItemId(item_id if isinstance(item_id, UUID) else UUID(item_id)),
        user_id=user_id,
        image_url=f"{user_id}/closet/{item_id}.jpg",
        tags=[],
    )


@pytest.mark.asyncio
async def test_get_upload_url_enforces_user_cap(monkeypatch):
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    monkeypatch.setenv("MAX_CLOSET_IMAGES_PER_USER", "1")
    get_settings.cache_clear()
    item = closet_item()
    await repo.create(item)

    use_case = GetUploadUrlUseCase(repo, storage)

    with pytest.raises(MaxClosetItemsExceeded):
        await use_case.execute(item.user_id, str(uuid4()))


@pytest.mark.asyncio
async def test_get_upload_url_returns_signed_url_under_cap(monkeypatch):
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    monkeypatch.setenv("MAX_CLOSET_IMAGES_PER_USER", "1")
    get_settings.cache_clear()
    item_id = str(uuid4())

    use_case = GetUploadUrlUseCase(repo, storage)

    upload_url = await use_case.execute("user-123", item_id)

    assert upload_url.startswith(f"http://storage/user-123/closet/{item_id}.jpg")


@pytest.mark.asyncio
async def test_register_writes_processing_item_and_enqueues_task():
    repo = FakeClosetRepo()
    queue = FakeTaskQueue()
    item_id = str(uuid4())

    result = await RegisterClothingItemUseCase(repo, queue).execute("user-123", item_id)

    item = await repo.get_by_id("user-123", ClothingItemId(UUID(item_id)))
    assert result == {"item_id": item_id, "status": "PROCESSING"}
    assert item.status == ClothingItemStatus.PROCESSING
    assert item.image_url == f"user-123/closet/{item_id}.jpg"
    assert queue.tasks == [
        (
            "embed-local",
            "/internal/tasks/process-upload",
            {"userId": "user-123", "item_id": item_id},
            0,
        )
    ]


@pytest.mark.asyncio
async def test_process_uploaded_item_marks_ready_and_indexes():
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    search = FakeEmbeddingSearch()
    item = closet_item()
    await repo.create(item)
    storage.bytes_by_path[item.image_url] = b"jpeg"

    await ProcessUploadedClothingItemUseCase(repo, search, storage, FakeGemini()).execute(
        item.user_id, str(item.id)
    )

    updated = await repo.get_by_id(item.user_id, item.id)
    assert updated.status == ClothingItemStatus.READY
    assert updated.category == "shirt"
    assert updated.colors == ["blue"]
    assert [tag.value for tag in updated.tags] == ["casual", "cotton"]
    assert search.indexed[0]["embedding"] == [0.1, 0.2, 0.3]
    assert search.indexed[0]["gender"] == "common"


@pytest.mark.asyncio
async def test_process_uploaded_item_marks_error_on_analysis_failure():
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    item = closet_item()
    await repo.create(item)
    storage.bytes_by_path[item.image_url] = b"jpeg"

    with pytest.raises(RuntimeError):
        await ProcessUploadedClothingItemUseCase(
            repo, FakeEmbeddingSearch(), storage, FakeGemini(fail_analysis=True)
        ).execute(item.user_id, str(item.id))

    updated = await repo.get_by_id(item.user_id, item.id)
    assert updated.status == ClothingItemStatus.ERROR


@pytest.mark.asyncio
async def test_process_uploaded_item_indexes_without_embedding_when_embedding_fails():
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    search = FakeEmbeddingSearch()
    item = closet_item()
    await repo.create(item)
    storage.bytes_by_path[item.image_url] = b"jpeg"

    await ProcessUploadedClothingItemUseCase(
        repo, search, storage, FakeGemini(fail_embedding=True)
    ).execute(item.user_id, str(item.id))

    updated = await repo.get_by_id(item.user_id, item.id)
    assert updated.status == ClothingItemStatus.READY
    assert search.indexed[0]["embedding"] is None


@pytest.mark.asyncio
async def test_delete_is_best_effort_for_storage_and_search():
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    storage.fail_delete = True
    search = FakeEmbeddingSearch()
    search.fail_delete = True
    item = closet_item()
    await repo.create(item)

    await DeleteClosetItemUseCase(repo, storage, search).execute(item.user_id, str(item.id))

    assert await repo.get_by_id(item.user_id, item.id) is None


@pytest.mark.asyncio
async def test_delete_missing_item_raises_not_found():
    with pytest.raises(ClosetItemNotFound):
        await DeleteClosetItemUseCase(
            FakeClosetRepo(), FakeImageStorage(), FakeEmbeddingSearch()
        ).execute("user-123", str(uuid4()))


@pytest.mark.asyncio
async def test_update_metadata_persists_and_reindexes_gender():
    repo = FakeClosetRepo()
    search = FakeEmbeddingSearch()
    item = closet_item()
    item.mark_ready("shirt", ["blue"], "spring", "common", [])
    await repo.create(item)

    await UpdateClosetItemMetadataUseCase(repo, search).execute(
        item.user_id,
        str(item.id),
        gender="female",
        tags=["formal"],
    )

    assert item.gender == "female"
    assert [tag.value for tag in item.tags] == ["formal"]
    assert search.indexed[0]["gender"] == "female"


@pytest.mark.asyncio
async def test_update_metadata_switches_ownership_status():
    repo = FakeClosetRepo()
    search = FakeEmbeddingSearch()
    item = closet_item()
    item.mark_ready("shirt", ["blue"], "spring", "common", [])
    item.set_ownership_status(ClosetOwnershipStatus.INTERESTING)
    await repo.create(item)

    result = await UpdateClosetItemMetadataUseCase(repo, search).execute(
        item.user_id,
        str(item.id),
        ownership_status="OWNED",
    )

    assert item.ownership_status == ClosetOwnershipStatus.OWNED
    assert item.status == ClothingItemStatus.READY
    assert result["ownershipStatus"] == "OWNED"
    assert search.indexed[0]["ownership_status"] == "OWNED"


class FakeStylingRepo:
    def __init__(self, session=None):
        self.session = session

    async def get_by_id(self, user_id, session_id):
        if self.session is None or self.session.user_id != user_id:
            return None
        return self.session


def proposing_session(user_id="user-123", candidates=None):
    return StyleSession(
        id=StyleSessionId(uuid4()),
        user_id=user_id,
        state=StyleSessionState.PROPOSING,
        proposed_candidates=candidates or [],
    )


def rakuten_candidate(item_id="rakuten:shop:1001"):
    return {
        "item_id": item_id,
        "source": "RAKUTEN",
        "name": "White T-Shirt",
        "image_url": "https://thumbnail.image.rakuten.co.jp/shop/1001.jpg",
        "price": 2980,
        "category": "top",
        "tags": ["casual"],
        "external_url": "https://item.rakuten.co.jp/shop/1001",
        "affiliate_url": "https://hb.afl.rakuten.co.jp/xyz",
        "shop_name": "Shop Name",
        "attribution": "Rakuten Ichiba",
    }


def import_use_case(styling_repo, closet_repo, storage, search):
    async def fetch(url):
        return b"external-jpeg"

    return ImportSuggestedClosetItemUseCase(
        styling_repo, closet_repo, storage, search, image_fetcher=fetch
    )


@pytest.mark.asyncio
async def test_import_suggestion_creates_interesting_ready_item():
    candidate = rakuten_candidate()
    session = proposing_session(candidates=[candidate])
    repo = FakeClosetRepo()
    storage = FakeImageStorage()
    search = FakeEmbeddingSearch()
    use_case = import_use_case(FakeStylingRepo(session), repo, storage, search)

    result = await use_case.execute("user-123", str(session.id), candidate["item_id"])

    items = await repo.get_all_by_user("user-123")
    assert len(items) == 1
    item = items[0]
    assert result == {
        "item_id": str(item.id),
        "status": "READY",
        "ownershipStatus": "INTERESTING",
    }
    assert item.status == ClothingItemStatus.READY
    assert item.ownership_status == ClosetOwnershipStatus.INTERESTING
    assert item.origin == "RAKUTEN"
    assert item.external_url == "https://item.rakuten.co.jp/shop/1001"
    assert item.price == 2980
    assert item.brand_or_shop == "Shop Name"
    assert [tag.value for tag in item.tags] == ["casual"]
    assert storage.bytes_by_path[f"user-123/closet/{item.id}.jpg"] == b"external-jpeg"
    assert search.indexed[0]["ownership_status"] == "INTERESTING"
    assert search.indexed[0]["origin"] == "RAKUTEN"
    assert search.indexed[0]["tags"] == ["casual"]
    assert search.indexed[0]["is_shared"] is False


@pytest.mark.asyncio
async def test_import_suggestion_rejects_unknown_candidate():
    session = proposing_session(candidates=[rakuten_candidate()])
    use_case = import_use_case(
        FakeStylingRepo(session), FakeClosetRepo(), FakeImageStorage(), FakeEmbeddingSearch()
    )

    with pytest.raises(ValueError, match="not proposed in this session"):
        await use_case.execute("user-123", str(session.id), "rakuten:other:999")


@pytest.mark.asyncio
async def test_import_suggestion_rejects_non_rakuten_candidate():
    candidate = {"item_id": "closet-1", "source": "CLOSET", "image_url": "http://x"}
    session = proposing_session(candidates=[candidate])
    use_case = import_use_case(
        FakeStylingRepo(session), FakeClosetRepo(), FakeImageStorage(), FakeEmbeddingSearch()
    )

    with pytest.raises(ValueError, match="Only RAKUTEN"):
        await use_case.execute("user-123", str(session.id), "closet-1")


@pytest.mark.asyncio
async def test_import_suggestion_rejects_other_users_session():
    session = proposing_session(user_id="other-user", candidates=[rakuten_candidate()])
    use_case = import_use_case(
        FakeStylingRepo(session), FakeClosetRepo(), FakeImageStorage(), FakeEmbeddingSearch()
    )

    with pytest.raises(StyleSessionNotFound):
        await use_case.execute("user-123", str(session.id), "rakuten:shop:1001")


@pytest.mark.asyncio
async def test_import_suggestion_enforces_closet_cap(monkeypatch):
    monkeypatch.setenv("MAX_CLOSET_IMAGES_PER_USER", "1")
    get_settings.cache_clear()
    candidate = rakuten_candidate()
    session = proposing_session(candidates=[candidate])
    repo = FakeClosetRepo()
    await repo.create(closet_item())
    use_case = import_use_case(
        FakeStylingRepo(session), repo, FakeImageStorage(), FakeEmbeddingSearch()
    )

    with pytest.raises(MaxClosetItemsExceeded):
        await use_case.execute("user-123", str(session.id), candidate["item_id"])


@pytest.mark.asyncio
async def test_update_metadata_rejects_unknown_ownership_status():
    repo = FakeClosetRepo()
    item = closet_item()
    item.mark_ready("shirt", ["blue"], "spring", "common", [])
    await repo.create(item)

    with pytest.raises(ValueError):
        await UpdateClosetItemMetadataUseCase(repo, FakeEmbeddingSearch()).execute(
            item.user_id,
            str(item.id),
            ownership_status="WISHLIST",
        )
