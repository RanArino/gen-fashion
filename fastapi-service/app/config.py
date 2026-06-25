from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_closet_images_per_user: int = 20

    google_cloud_project: str | None = None
    firebase_project_id: str | None = None
    firestore_database_id: str = "(default)"
    firestore_emulator_host: str | None = None
    firebase_auth_emulator_host: str | None = None

    gemini_api_key: str | None = None
    google_genai_api_key: str | None = None
    google_genai_use_vertexai: bool = False
    image_analysis_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_host: str | None = None
    elasticsearch_api_key: str | None = None
    clothing_items_index: str = "clothing_items"

    r2_endpoint_url: str | None = None
    r2_public_endpoint_url: str | None = None
    r2_account_id: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "gen-fashion-images"

    task_queue_mode: str = "local"
    cloud_tasks_queue_embed: str | None = None
    cloud_tasks_location: str = "asia-northeast1"
    adk_internal_base_url: str = "http://localhost:3000"
    # Base URL of the fastapi-service itself, used to reach its own /internal/*
    # worker routes (e.g. /internal/tasks/process-upload). Distinct from
    # adk_internal_base_url (the ADK run-session target). Falls back to
    # adk_internal_base_url when unset to preserve older single-URL behavior.
    fastapi_internal_base_url: str | None = None

    # Shared secret guarding the /internal/* worker routes. Sent by the task
    # producers (LocalHttpTaskQueueAdapter / CloudTasksAdapter) and verified by
    # require_internal_secret. Unset => the internal routes are locked (503).
    # Deployment hardening (OIDC + Cloud Run internal ingress) is a separate,
    # BLOCKING deploy gate — see the M2 ExecPlan Decision Log.
    internal_task_secret: str | None = None

    @property
    def project_id(self) -> str:
        return self.google_cloud_project or self.firebase_project_id or "gen-fashion-local"

    @property
    def auth_project_id(self) -> str:
        return self.firebase_project_id or self.project_id

    @property
    def firestore_project_id(self) -> str:
        # Firestore data lives in the Firebase project (same namespace the
        # frontend + auth use), which differs from the Vertex AI / compute
        # project (google_cloud_project) in local dev. In production all three
        # are the same project, so this is a no-op there.
        return self.firebase_project_id or self.project_id

    @property
    def resolved_elasticsearch_url(self) -> str:
        if self.elasticsearch_host and self.elasticsearch_url == "http://localhost:9200":
            host = self.elasticsearch_host
            if host.startswith("http://") or host.startswith("https://"):
                return host
            return f"http://{host}"
        return self.elasticsearch_url

    @property
    def resolved_gemini_api_key(self) -> str | None:
        return self.gemini_api_key or self.google_genai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
