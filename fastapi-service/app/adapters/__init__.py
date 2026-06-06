from app.adapters.firestore_closet_repo import FirestoreClosetRepository
from app.adapters.firestore_styling_repo import FirestoreStylingRepository
from app.adapters.elasticsearch_embedding_repo import ElasticsearchEmbeddingRepository
from app.adapters.r2_image_storage import R2ImageStorage
from app.adapters.cloud_tasks_adapter import CloudTasksAdapter
from app.adapters.local_task_queue import LocalHttpTaskQueueAdapter
from app.adapters.gemini_analysis import GeminiAnalysisAdapter
from app.adapters.shared_closet_search import SharedClosetSearchAdapter
from app.adapters.image_generation_stub import ImageGenerationStub

__all__ = [
    "FirestoreClosetRepository",
    "FirestoreStylingRepository",
    "ElasticsearchEmbeddingRepository",
    "R2ImageStorage",
    "CloudTasksAdapter",
    "LocalHttpTaskQueueAdapter",
    "GeminiAnalysisAdapter",
    "SharedClosetSearchAdapter",
    "ImageGenerationStub",
]
