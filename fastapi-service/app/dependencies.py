from app.adapters import (
    FirestoreClosetRepository,
    FirestoreStylingRepository,
    ElasticsearchEmbeddingRepository,
    R2ImageStorage,
    CloudTasksAdapter,
    LocalHttpTaskQueueAdapter,
    GeminiAnalysisAdapter,
    SharedClosetSearchAdapter,
    ImageGenerationStub,
)
from app.config import get_settings
from app.ports import (
    ClosetRepositoryPort,
    StylingRepositoryPort,
    EmbeddingSearchPort,
    ClothingSearchPort,
    ImageStoragePort,
    TaskQueuePort,
    ImageGenerationPort,
    GeminiAnalysisPort,
)
from app.use_cases.closet import (
    DeleteClosetItemUseCase,
    GetUploadUrlUseCase,
    ProcessUploadedClothingItemUseCase,
    RegisterClothingItemUseCase,
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
    settings = get_settings()
    if settings.task_queue_mode == "cloud_tasks" and settings.google_cloud_project:
        return CloudTasksAdapter()
    return LocalHttpTaskQueueAdapter()


def get_image_generation() -> ImageGenerationPort:
    return ImageGenerationStub()


def get_gemini_analysis() -> GeminiAnalysisPort:
    return GeminiAnalysisAdapter()


def get_upload_url_use_case() -> GetUploadUrlUseCase:
    return GetUploadUrlUseCase(get_closet_repository(), get_image_storage())


def get_register_clothing_item_use_case() -> RegisterClothingItemUseCase:
    return RegisterClothingItemUseCase(get_closet_repository(), get_task_queue())


def get_delete_closet_item_use_case() -> DeleteClosetItemUseCase:
    return DeleteClosetItemUseCase(
        get_closet_repository(),
        get_image_storage(),
        get_embedding_search(),
    )


def get_process_uploaded_item_use_case() -> ProcessUploadedClothingItemUseCase:
    return ProcessUploadedClothingItemUseCase(
        get_closet_repository(),
        get_embedding_search(),
        get_image_storage(),
        get_gemini_analysis(),
    )
