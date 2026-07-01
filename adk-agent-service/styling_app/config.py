import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Env config for the ADK agent service (M4-9).

    Mirrors the model IDs / index / R2 names pinned in
    fastapi-service/app/config.py so both services hit the same backends.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # req §7.1 / §12.2: all agents default to gemini-2.0-flash, overridable.
    # On Vertex AI use AGENT_MODEL=gemini-2.5-flash (M1-4: 2.0-flash absent there).
    agent_model: str = "gemini-2.0-flash"

    google_cloud_project: str | None = None
    firebase_project_id: str | None = None
    google_cloud_location: str = "us-central1"
    gemini_api_key: str | None = None
    google_genai_api_key: str | None = None
    google_genai_use_vertexai: bool = False

    image_analysis_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    image_generation_model: str = "gemini-2.5-flash-image"

    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_api_key: str | None = None
    elasticsearch_ca_certs: str | None = None
    elasticsearch_ssl_assert_fingerprint: str | None = None
    clothing_items_index: str = "clothing_items"

    firestore_database_id: str = "(default)"
    firestore_emulator_host: str | None = None

    r2_endpoint_url: str | None = None
    r2_public_endpoint_url: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str = "gen-fashion-images"

    internal_task_secret: str | None = None

    # Wall-clock budget for the ADK agent run before falling back to the
    # deterministic coordination path. 45s was too tight on cold start; 90s
    # gives the primary LLM path more room. MUST stay below the fastapi SSE
    # bound (STREAM_MAX_SECONDS) minus the deterministic-fallback time, so the
    # client always sees COMPLETED rather than a stream TIMEOUT.
    adk_run_timeout_seconds: int = 90

    @property
    def project_id(self) -> str:
        return self.google_cloud_project or "gen-fashion-local"

    @property
    def firestore_project_id(self) -> str:
        # Firestore data lives in the Firebase project (same namespace the
        # frontend + fastapi-service use), which differs from the Vertex AI /
        # compute project (google_cloud_project) in local dev. In production
        # all three are the same project, so this is a no-op there.
        return self.firebase_project_id or self.project_id

    @property
    def resolved_gemini_api_key(self) -> str | None:
        return self.gemini_api_key or self.google_genai_api_key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # ADK's Gemini integration reads GOOGLE_API_KEY / GOOGLE_GENAI_USE_VERTEXAI
    # from the process env; bridge our settings so one .env drives both.
    if settings.google_genai_use_vertexai:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        if settings.google_cloud_project:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_location)
    elif settings.resolved_gemini_api_key:
        os.environ.setdefault("GOOGLE_API_KEY", settings.resolved_gemini_api_key)
    return settings
