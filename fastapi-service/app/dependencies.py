from app.adapters import (
    FirestoreClosetRepository,
    FirestoreStylingRepository,
    ElasticsearchEmbeddingRepository,
    R2ImageStorage,
    CloudTasksAdapter,
    SharedClosetSearchAdapter,
    ImageGenerationStub,
)
from app.ports import (
    ClosetRepositoryPort,
    StylingRepositoryPort,
    EmbeddingSearchPort,
    ClothingSearchPort,
    ImageStoragePort,
    TaskQueuePort,
    ImageGenerationPort,
)


def get_closet_repository() -> ClosetRepositoryPort:
    return FirestoreClosetRepository()


def get_styling_repository() -> StylingRepositoryPort:
    return FirestoreStylingRepository()


def get_embedding_search() -> EmbeddingSearchPort:
    return ElasticsearchEmbeddingRepository()


def get_clothing_search() -> ClothingSearchPort:
    return SharedClosetSearchAdapter()


def get_image_storage() -> ImageStoragePort:
    return R2ImageStorage()


def get_task_queue() -> TaskQueuePort:
    return CloudTasksAdapter()


def get_image_generation() -> ImageGenerationPort:
    return ImageGenerationStub()
