# M2 — Closet Management Backend & Async Embedding Pipeline


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


After this milestone, an authenticated user can put a clothing photo into the system and have it become a fully analyzed, searchable closet item — entirely through the backend HTTP API, provable from a terminal without any frontend.

Concretely, the following becomes possible where today every endpoint returns HTTP 501:

1. The client asks for a place to upload (`GET /closet/upload-url`). The API checks the user is under their item cap and returns a 15-minute signed `PUT` URL pointing at object storage.
2. The client uploads the bytes directly to storage, then tells the API it finished (`POST /closet/items/{item_id}/complete`). The API writes a Firestore placeholder document with `status: "PROCESSING"` and enqueues a background job.
3. The background job (`POST /internal/tasks/process-upload`) fetches the image, runs Gemini image analysis to extract `{category, colors, tags, season, style}`, generates an embedding, flips the Firestore document to `status: "READY"`, and indexes the item in Elasticsearch.
4. The client can delete an item (`DELETE /closet/items/{item_id}`), which removes it from Firestore, Elasticsearch, and object storage.

This is the **backend slice of milestone M2** (`docs/feature-matrix-phase01.md`). It covers nine requirements: M2-2, M2-3, M2-4, M2-5, M2-6, M2-7, M2-8, M2-9, M2-10. The three client-facing requirements in M2 — M2-1 (Flutter Google Sign-In), M2-11 (Flutter closet UI), M2-12 (Firebase Security Rules) — are **deferred to a follow-up plan** because no Flutter application exists in the repository yet (there is no `pubspec.yaml`). The backend built here is the API those client pieces will consume, and it is the exact set of requirements whose stubs already live in `fastapi-service` (each stub is annotated `Implement in M2-N`). See the Decision Log for the scope rationale.

**Why it matters:** M3 (Shared Demo Closet), M4 (ADK Agents Core), and M5 (Web E2E) all assume that closet items exist in Firestore + Elasticsearch with analysis metadata and embeddings. This milestone is the pipeline that produces that data. Until it exists, every downstream search and coordination feature has nothing to search over.

**Acceptance (observable):** Against the local stack started by `make dev`, a scripted run uploads a real JPEG to storage via the signed URL, completes registration, lets the worker run, and then observes (a) a Firestore document at `users/{uid}/closet/{itemId}` with `status: "READY"` and populated `category`/`tags`/`colors`/`season`, (b) a matching document in the Elasticsearch `clothing_items` index, and (c) the bytes present in storage. A subsequent `DELETE` removes the item from all three. `pytest` passes, including new use-case unit tests. Full validation steps are in *Validation and Acceptance*.


## Progress


- [ ] Phase 0 — Foundations: dependencies, central config, env reconciliation, `ClothingItem` lifecycle fields.
- [ ] Phase 1 — Firebase ID-token middleware (M2-2) with a test-friendly override.
- [ ] Phase 2 — Output adapters: R2/S3 storage (M2-7), Firestore closet repo (M2-8), Elasticsearch repo (M2-9, keyword-first), task queue (M2-10, local + Cloud Tasks).
- [ ] Phase 3 — Use cases: get-upload-url (M2-3), register (M2-4), delete (M2-6), process-upload worker (M2-5).
- [ ] Phase 4 — HTTP wiring: closet routes + new internal-tasks router, dependency providers.
- [ ] Phase 5 — Tests and local end-to-end validation; flip the nine matrix rows from 🟡 to ✅ only when their acceptance is met.


## Surprises & Discoveries


- (2026-06-04, planning) **`adk-agent-service` is TypeScript, not Python.** Its `src/` contains `.ts` stubs and `package.json` lists only `typescript`/`@types/node` with empty `dependencies`. Requirement §6.9 places `ProcessUploadedClothingItemUseCase` in `adk-agent-service`, but the Python stub for it already lives at `fastapi-service/app/use_cases/closet/process_uploaded_item.py`, and `fastapi-service` already has the Firestore/Elasticsearch ports and adapters it needs. See Decision Log for where the worker lands.
- (2026-06-04, planning) **Env var names diverge between the running config and the spec.** Root `.env.example` and `docker-compose.yml` use `ELASTICSEARCH_HOST`, `FIREBASE_PROJECT_ID`, `GOOGLE_GENAI_API_KEY`, and `MAX_CLOSET_IMAGES_PER_USER=50`, while req §9.4/§12.2 specify `ELASTICSEARCH_URL`, `GOOGLE_CLOUD_PROJECT`, `GEMINI_API_KEY`/`GOOGLE_GENAI_USE_VERTEXAI`, and a default of `20`. Phase 0 reconciles these in one place.
- (2026-06-04, planning) **`EmbeddingSearchPort.index_item(item_id, user_id, embedding)` cannot carry the index document.** The Elasticsearch `clothing_items` mapping (§8.2) needs `tags`, `category`, `colors`, `season`, `is_shared` as well. The port signature must widen (Phase 2 / Decision Log).
- (Carried from M1, relevant here) **Gemini model availability is backend-dependent.** Per the M1 plan, `gemini-2.0-flash` is reachable via the developer API (`GEMINI_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=false`) but was *absent* from Vertex `models.list()` for this project, where `gemini-2.5-flash` is available. The analysis model is therefore env-configurable.


## Decision Log


- Decision: **Scope this plan to the M2 backend (M2-2…M2-10); defer M2-1, M2-11, M2-12 to a separate frontend plan.**
  Rationale: The repository has no Flutter project, so Google Sign-In, the closet UI, and the Firebase Security Rules that pair with a client's direct Firestore reads cannot be implemented or verified yet. The nine backend requirements form a self-contained unit that is provable from the command line against `make dev`, and all nine already have stubs in `fastapi-service`. M2's stated exit criterion ("a logged-in user uploads an image → … → delete removes all three") is satisfied at the API layer here; the Flutter client consumes this API later.
  Date/Author: 2026-06-04 / planning agent.

- Decision: **Implement `ProcessUploadedClothingItemUseCase` (M2-5) as an internal endpoint inside `fastapi-service`, not `adk-agent-service`.**
  Rationale: §6.9 assigns the worker to `adk-agent-service` on the grounds that it "calls Gemini/Elasticsearch/Firestore directly without ADK." But `adk-agent-service` is a TypeScript skeleton with no dependencies, while `fastapi-service` already owns the Python Firestore and Elasticsearch adapters and the `process_uploaded_item.py` stub. Re-implementing the Gemini+ES+Firestore stack in TypeScript would duplicate working Python infrastructure for no MVP benefit. The worker is exposed as `POST /internal/tasks/process-upload` in `fastapi-service`. This is a documented divergence from §6.9's container assignment; the behavior and contract are unchanged.
  Rollback: if the agent service later needs to own embedding, the use case is a thin orchestration over ports and can be reimplemented behind the same internal HTTP contract.
  Date/Author: 2026-06-04 / planning agent.

- Decision: **Two adapters behind `TaskQueuePort` (M2-10), selected by environment.** A `LocalHttpTaskQueueAdapter` (default in local dev) calls the internal worker endpoint over HTTP so the full pipeline runs without GCP; a `CloudTasksAdapter` (used when `GOOGLE_CLOUD_PROJECT` is set and `TASK_QUEUE_MODE != local`) enqueues to `CLOUD_TASKS_QUEUE_EMBED`.
  Rationale: Cloud Tasks has no local emulator. A port-level swap keeps the use cases unaware of the difference and makes M2 demoable locally.
  Date/Author: 2026-06-04 / planning agent.

- Decision: **Use one S3-compatible storage adapter (boto3) for both Cloudflare R2 and a local MinIO stand-in (M2-7).** Local `make dev` gets a MinIO service; the adapter targets it via `R2_ENDPOINT_URL`. Staging/production point the same adapter at `https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com`.
  Rationale: R2 is S3-compatible and has no emulator. MinIO supports presigned PUT URLs and CORS, so the signed-URL upload path is verifiable locally with no Cloudflare credentials. One adapter, swapped by endpoint.
  Date/Author: 2026-06-04 / planning agent.

- Decision: **Keyword-first Elasticsearch adapter (M2-9); vectors are written but not queried in M2.** The `clothing_items` index is created with the full §8.2 mapping (including `dense_vector` dims=768). `index_item` upserts the keyword fields plus the embedding when one is available; `delete_item` removes by id. Vector/hybrid `knn` search and the GCE-hosted ES are deferred to the deployment phase, consistent with the M1-3 re-scope decision.
  Rationale: M2's exit criteria require indexing and deletion, not search (search is M5-5). The M1 plan already deferred vector hybrid + GCE.
  Date/Author: 2026-06-04 / planning agent.

- Decision: **Embedding generation in M2-5 is best-effort.** If the embedding model call succeeds, attach an `ImageEmbedding` and write the vector to Elasticsearch; if it fails or the model is unavailable, log it, set the Firestore document to `READY` anyway, and index the keyword fields with no vector. The item is never stuck in `PROCESSING` solely because vectors are deferred.
  Rationale: Per M1-3, vector search is off the MVP critical path; the exact `gemini-embedding-2` image-embedding call is the one genuine unknown (see Interfaces and Dependencies). Decoupling `READY` from embedding success protects the demo path.
  Date/Author: 2026-06-04 / planning agent.


## Outcomes & Retrospective


(To be completed at milestone end. Record which of M2-2…M2-10 reached ✅, the measured timings of the worker, the resolved `gemini-embedding-2` call, and any adapter surprises.)


## Context and Orientation


### Current State


M0 and M1 are complete. `/Users/ran/my-app/gen-fashion/` holds a hexagonal Python service (`fastapi-service`), a TypeScript ADK skeleton (`adk-agent-service`), PoC scripts under `poc/`, and `docker-compose.yml` that boots Elasticsearch 8.11 (`localhost:9200`) and the Firestore emulator (`localhost:8080`).

In `fastapi-service`, the M2 surface area exists only as stubs:

- Ports (`app/ports/`) are defined abstract classes: `ClosetRepositoryPort`, `EmbeddingSearchPort`, `ImageStoragePort`, `TaskQueuePort`, plus `ClothingSearchPort`, `StylingRepositoryPort`, `ImageGenerationPort`.
- Adapters (`app/adapters/`) subclass the ports but every method raises `NotImplementedError("Implement in M2-N: …")`: `r2_image_storage.py`, `firestore_closet_repo.py`, `elasticsearch_embedding_repo.py`, `cloud_tasks_adapter.py`.
- Use cases (`app/use_cases/closet/`) are constructor-wired classes whose `execute()` raises `NotImplementedError`: `get_upload_url.py`, `register_clothing_item.py`, `process_uploaded_item.py`, `delete_closet_item.py`.
- Routes (`app/handlers/closet_routes.py`) return `HTTPException(501, "Implement in M2-N")` for `GET /closet/upload-url`, `POST /closet/items/{item_id}/complete`, `DELETE /closet/items/{item_id}`.
- DI providers (`app/dependencies.py`) already return the adapter classes (e.g. `get_image_storage() -> R2ImageStorage()`), so wiring is mostly about filling adapters in, not rebuilding the graph.

The domain model `ClothingItem` (`app/domain/closet/aggregates.py`) currently has `id`, `user_id`, `image_url`, `tags`, `embedding`, `created_at`, `updated_at`. It has **no** processing `status`, `category`, `colors`, or `season` — fields the Firestore document (§8.1) requires. Phase 0 adds them.

`fastapi-service/requirements.txt` has `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `elasticsearch==8.11.0`, `firebase-admin==6.2.0`, `google-cloud-tasks==2.14.0`, `httpx`, `pytest`, `pytest-asyncio`, `python-multipart`. It lacks `boto3` (R2/S3) and `google-genai` (Gemini analysis + embedding). `google-cloud-firestore` arrives transitively via `firebase-admin`.


### Architecture Glossary


- **Hexagonal port / adapter** — A *port* is an abstract interface in `app/ports/`; an *adapter* in `app/adapters/` is a concrete implementation. Use cases depend only on ports, so infrastructure (R2, Firestore, ES, Cloud Tasks) is swappable. Honor this: do not import `boto3`, `elasticsearch`, or `firebase_admin` inside `app/use_cases/`.
- **Cloudflare R2** — S3-compatible object storage. Reached with the AWS SDK (`boto3`) by overriding `endpoint_url`. Stores closet images at key `{userId}/closet/{itemId}.jpg` in bucket `gen-fashion-images` (§8.4).
- **Signed PUT URL** — A time-limited URL that authorizes a single `PUT` to one object key. The client uploads bytes straight to storage; the API never proxies the file (ADL-014). TTL is 15 minutes (§6.7).
- **Firestore emulator** — A local stand-in for Firestore at `localhost:8080`. The Google client libraries route to it automatically when `FIRESTORE_EMULATOR_HOST` is set. No GCP credentials needed locally.
- **Cloud Tasks** — GCP managed queue used in production to run the embedding job asynchronously (ADL-002). No local emulator exists; locally the `LocalHttpTaskQueueAdapter` calls the worker endpoint directly (Decision Log).
- **`ProcessUploadedClothingItemUseCase` worker** — The asynchronous step that turns an uploaded image into a `READY`, indexed item. Triggered by a queued job hitting `POST /internal/tasks/process-upload`.
- **`clothing_items` index** — The single Elasticsearch index holding both user and shared closet items, distinguished by `user_id` / `is_shared` (§8.2).
- **Structured output** — Gemini constrained to emit JSON matching a schema. Used so `analyze_clothing_image` returns a typed `ClothingAnalysisResult` rather than free text (§6.1).


### Key Files and Paths


- `docs/feature-matrix-phase01.md` — Milestone tracker. The rows M2-2…M2-10 are flipped to 🟡 in the same change that introduces this plan, and to ✅ one at a time only when each item's acceptance is met. M2-1, M2-11, M2-12 stay ❌ with a deferral note.
- `docs/plans/20260604-m2-closet-management-backend.md` (this file) — Update its `Progress`, `Surprises & Discoveries`, and `Decision Log` in the same change as any matrix flip. Never update one without the other.
- `docs/req-phase01.md` §6.7–6.10, §8.1–8.4, §10.3, §12.2, ADL-002, ADL-014, ADL-015 — Source requirements for this milestone.
- `fastapi-service/app/` — All implementation lands here. Do not touch `adk-agent-service/` or `poc/`.
- `docker-compose.yml`, root `.env.example`, `Makefile` — Local stack; Phase 0 reconciles env vars and adds a MinIO service.


## Plan of Work


The order is deliberate: foundations first (deps, config, domain), then ports' adapters bottom-up, then use cases, then HTTP wiring, then validation. Each phase leaves the service importable and `pytest`-green.


### Phase 0 — Foundations


Add the two missing libraries to both `fastapi-service/requirements.txt` and the `[project].dependencies` list in `fastapi-service/pyproject.toml`:

    boto3==1.34.0
    google-genai==0.3.0
    google-cloud-firestore==2.13.1

(`google-cloud-firestore` is pinned explicitly so the async client is guaranteed present even if `firebase-admin`'s transitive pin shifts. Confirm exact patch versions resolve at install time and adjust if pip reports a conflict — record any change in Surprises.)

Create a single typed settings module `fastapi-service/app/config.py` using `pydantic-settings` (already a dependency), so configuration is read in one place instead of ad hoc `os.getenv` calls scattered across modules:

    from functools import lru_cache
    from pydantic_settings import BaseSettings, SettingsConfigDict


    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")

        # Limits
        max_closet_images_per_user: int = 20

        # GCP / Firebase
        google_cloud_project: str | None = None
        firestore_database_id: str = "(default)"
        firestore_emulator_host: str | None = None
        firebase_auth_emulator_host: str | None = None

        # Gemini
        gemini_api_key: str | None = None
        google_genai_use_vertexai: bool = False
        image_analysis_model: str = "gemini-2.0-flash"
        embedding_model: str = "gemini-embedding-2"
        embedding_dimensions: int = 768

        # Elasticsearch
        elasticsearch_url: str = "http://localhost:9200"
        elasticsearch_api_key: str | None = None
        clothing_items_index: str = "clothing_items"

        # R2 / S3
        r2_endpoint_url: str | None = None
        r2_account_id: str | None = None
        r2_access_key_id: str | None = None
        r2_secret_access_key: str | None = None
        r2_bucket_name: str = "gen-fashion-images"

        # Task queue
        task_queue_mode: str = "local"  # "local" | "cloud_tasks"
        cloud_tasks_queue_embed: str | None = None
        cloud_tasks_location: str = "asia-northeast1"
        adk_internal_base_url: str = "http://localhost:8000"


    @lru_cache
    def get_settings() -> Settings:
        return Settings()

Reconcile the running config with the spec. In root `.env.example` and the `fastapi-service` block of `docker-compose.yml`, rename `ELASTICSEARCH_HOST`→`ELASTICSEARCH_URL` (full URL form `http://elasticsearch:9200`), keep `GOOGLE_CLOUD_PROJECT` (add it), set `MAX_CLOSET_IMAGES_PER_USER=20`, and add the R2/MinIO and task-queue variables. Add a MinIO service to `docker-compose.yml` (see Concrete Steps) and point `R2_ENDPOINT_URL` at it for local dev. Keep `GOOGLE_GENAI_USE_VERTEXAI=false` locally (developer API key) per §9.4.

Extend the domain to model the processing lifecycle. In `app/domain/closet/value_objects.py` add:

    from enum import Enum

    class ClothingItemStatus(str, Enum):
        PROCESSING = "PROCESSING"
        READY = "READY"
        ERROR = "ERROR"

In `app/domain/closet/aggregates.py` add fields to `ClothingItem` with defaults so existing construction sites and tests keep working (the current tests build `ClothingItem(id=, user_id=, image_url=, tags=[])` positionally-by-keyword):

    status: ClothingItemStatus = ClothingItemStatus.PROCESSING
    category: Optional[str] = None
    colors: List[str] = field(default_factory=list)
    season: Optional[str] = None

Add lifecycle methods `mark_ready(category, colors, season, tags, embedding)` and `mark_error()` that set the fields and call `_mark_updated()`. Keep the aggregate pure (no I/O). This is additive to M0-2; the matrix row for M0-2 stays ✅.


### Phase 1 — Firebase ID-token middleware (M2-2)


Create `fastapi-service/app/auth.py`. Initialize the Firebase Admin app once (idempotently) and expose a FastAPI dependency that verifies the bearer token and returns the uid:

    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
    from fastapi import Depends, HTTPException
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from app.config import get_settings

    _bearer = HTTPBearer(auto_error=True)


    def _ensure_app() -> None:
        if not firebase_admin._apps:
            settings = get_settings()
            project = settings.google_cloud_project or "gen-fashion-local"
            firebase_admin.initialize_app(options={"projectId": project})


    async def verify_firebase_token(
        creds: HTTPAuthorizationCredentials = Depends(_bearer),
    ) -> str:
        _ensure_app()
        try:
            decoded = firebase_auth.verify_id_token(creds.credentials)
            return decoded["uid"]
        except Exception as exc:  # noqa: BLE001 - surface as 401 per §10.3
            raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

Note the matrix and §10.3 reference `HTTPAuthCredentials`/`HTTPBearer`; the correct FastAPI symbol is `HTTPAuthorizationCredentials`. Use the correct name.

Local/testing strategy: `docker-compose.yml` runs only the Firestore emulator, not the Auth emulator, so real `verify_id_token` cannot validate locally-minted tokens. For tests, use FastAPI `app.dependency_overrides[verify_firebase_token] = lambda: "test-user-123"`. For local manual runs, set `FIREBASE_AUTH_EMULATOR_HOST` if the team adds the Auth emulator, otherwise drive the internal worker and Firestore/ES assertions directly (the upload-url and register endpoints can be exercised with a stub override via an env-gated `DEV_AUTH_BYPASS` — implement only if needed and never enable it when `GOOGLE_CLOUD_PROJECT` is set). Record the chosen local approach in Surprises.


### Phase 2 — Output adapters


**M2-7 `R2ImageStorage` (`app/adapters/r2_image_storage.py`).** Build a boto3 S3 client against R2/MinIO and implement the four methods. `image_path` is the object key `{userId}/closet/{itemId}.jpg`.

    import boto3
    from botocore.config import Config
    from app.config import get_settings
    from app.ports import ImageStoragePort


    class R2ImageStorage(ImageStoragePort):
        def __init__(self) -> None:
            s = get_settings()
            self._bucket = s.r2_bucket_name
            self._client = boto3.client(
                "s3",
                endpoint_url=s.r2_endpoint_url,
                aws_access_key_id=s.r2_access_key_id,
                aws_secret_access_key=s.r2_secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )

        def _key(self, user_id: str, item_id: str) -> str:
            return f"{user_id}/closet/{item_id}.jpg"

        async def get_signed_upload_url(self, user_id, item_id, expiration_seconds=900) -> str:
            return self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": self._key(user_id, item_id),
                        "ContentType": "image/jpeg"},
                ExpiresIn=expiration_seconds,
            )

        async def get_download_url(self, image_path) -> str:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": image_path},
                ExpiresIn=3600,
            )

        async def delete_image(self, image_path) -> None:
            self._client.delete_object(Bucket=self._bucket, Key=image_path)

        async def verify_image_exists(self, image_path) -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=image_path)
                return True
            except self._client.exceptions.ClientError:
                return False

    Add a method to fetch bytes for the worker (extend `ImageStoragePort` with `get_image_bytes(image_path) -> bytes`, implemented as `get_object(...)["Body"].read()`). boto3 is synchronous; these calls are short and acceptable inside async methods for MVP. The signed-PUT `ContentType` must match the header the client sends (`Content-Type: image/jpeg`). Configure bucket CORS once (Concrete Steps) so browser preflight + PUT succeed (§8.4, ADL-014).

**M2-8 `FirestoreClosetRepository` (`app/adapters/firestore_closet_repo.py`).** Use `google.cloud.firestore.AsyncClient`. Documents live at `users/{userId}/closet/{itemId}` (§8.1). Map between the Firestore document shape (`status`, `imageUrl`, `category`, `tags`, `season`, `colors`, `embeddingId`, `createdAt`) and the `ClothingItem` aggregate. Implement `create`, `get_by_id`, `get_all_by_user`, `update`, `delete`, `count_by_user`. For `count_by_user`, use the collection's `count()` aggregation. The client honors `FIRESTORE_EMULATOR_HOST` automatically. Keep Firestore-document field names (camelCase) isolated to this adapter; the domain stays snake_case.

**M2-9 `ElasticsearchEmbeddingRepository` (`app/adapters/elasticsearch_embedding_repo.py`).** Use `elasticsearch.AsyncElasticsearch(hosts=[settings.elasticsearch_url], api_key=...)`. Add an idempotent `ensure_index()` that creates `clothing_items` with the §8.2 mapping if absent (call it at startup). **Widen the port** `EmbeddingSearchPort.index_item` to carry the document:

    async def index_item(self, item_id: str, user_id: str, *, is_shared: bool,
                         tags: list[str], category: str | None, colors: list[str],
                         season: str | None, embedding: list[float] | None) -> None: ...

Implement `index_item` as an upsert keyed by `item_id` (omit the `embedding` field when `None`), `delete_item` as a delete-by-id that ignores 404, and keep `search_similar` minimal (filter by `user_id`; vector `knn` is M5). Update the abstract `EmbeddingSearchPort` signature and the docstrings to match; this is the one intentional port change in M2 (Decision Log).

**M2-10 task queue (`app/adapters/cloud_tasks_adapter.py` + new `app/adapters/local_task_queue.py`).** Implement `CloudTasksAdapter.enqueue_task` with `google.cloud.tasks_v2` to create an HTTP task POSTing the JSON payload to `{adk_internal_base_url}{handler_path}` on `CLOUD_TASKS_QUEUE_EMBED`. Add `LocalHttpTaskQueueAdapter` that, on `enqueue_task`, fires an `httpx.AsyncClient().post(...)` to the same URL (await it for deterministic local tests, or schedule it; await is simpler and fine locally). `get_task_status` can return a static `"UNKNOWN"` for MVP. Selection happens in `app/dependencies.py` (Phase 4).


### Phase 3 — Use cases


All use cases depend only on ports and never import infrastructure libraries.

**M2-3 `GetUploadUrlUseCase` (§6.7).** `execute(user_id, item_id)`: if `closet_repo.count_by_user(user_id) >= settings.max_closet_images_per_user`, raise a domain `MaxClosetItemsExceeded` (mapped to HTTP 429 by the route); else return `image_storage.get_signed_upload_url(user_id, item_id)`. No Firestore write here.

**M2-4 `RegisterClothingItemUseCase` (§6.8).** `execute(user_id, item_id)`: build a `ClothingItem` with `status=PROCESSING` and `image_url="{user_id}/closet/{item_id}.jpg"`, `closet_repo.create(item)`, then `task_queue.enqueue_task(queue_name=settings.cloud_tasks_queue_embed or "embed-local", handler_path="/internal/tasks/process-upload", payload={"userId": user_id, "item_id": item_id})`. Return `{item_id, status: "PROCESSING"}`. (The current stub signature includes `image_url`; derive it from the key convention instead and drop the unused parameter, or keep it optional — pick one and keep the route consistent.)

**M2-6 `DeleteClosetItemUseCase` (§6.10, ADL-015).** `execute(user_id, item_id)`: if `closet_repo.get_by_id` is `None`, raise `ClosetItemNotFound` (route → 404). Then best-effort `embedding_search.delete_item(item_id, user_id)` and `image_storage.delete_image(key)` (log and swallow their failures), and finally `closet_repo.delete(user_id, item_id)` which must succeed. Orphaned R2/ES data is acceptable for MVP (§6.10).

**M2-5 `ProcessUploadedClothingItemUseCase` (§6.9).** Constructor takes `closet_repo`, `embedding_search`, `image_storage`, and a `GeminiAnalysisPort` (new — see below). `execute(user_id, item_id)`:

1. `image_bytes = await image_storage.get_image_bytes("{user_id}/closet/{item_id}.jpg")`.
2. `analysis = await gemini.analyze(image_bytes)` → `ClothingAnalysisResult{category, colors, tags, season, style}`.
3. `embedding = await gemini.embed(image_bytes)` wrapped in try/except (best-effort; `None` on failure — Decision Log).
4. Load the item, `item.mark_ready(...)`, `closet_repo.update(item)` (status `READY`, metadata, `embeddingId=item_id`).
5. `embedding_search.index_item(item_id, user_id, is_shared=False, tags=..., category=..., colors=..., season=..., embedding=embedding_vector_or_None)`.
6. On any exception in steps 1–2 (the parts that must succeed), set the Firestore doc to `status="ERROR"` and re-raise so Cloud Tasks retries (§6.9 failure handling). A delete that raced ahead (doc missing) is ignored (§6.10 note).

Define `ClothingAnalysisResult` as a Pydantic `BaseModel` in the application layer (e.g. top of `process_uploaded_item.py` or a small `app/use_cases/closet/schemas.py`). Introduce a `GeminiAnalysisPort` in `app/ports/` with `analyze(image_bytes) -> ClothingAnalysisResult` and `embed(image_bytes) -> list[float]`, and a `GeminiAnalysisAdapter` in `app/adapters/` using `google-genai`:

- Analysis: `client.models.generate_content(model=settings.image_analysis_model, contents=[image_part, prompt], config={"response_mime_type": "application/json", "response_schema": ClothingAnalysisResult})`. Local dev passes `api_key=settings.gemini_api_key`; production sets `GOOGLE_GENAI_USE_VERTEXAI=true` and relies on ADC.
- Embedding: call the embedding model with `output_dimensionality=settings.embedding_dimensions` (768). Treat the exact `gemini-embedding-2` image-embedding call as unverified — see Interfaces and Dependencies; on `NotImplementedError`/API error, return no vector and let the worker proceed (Decision Log).

Keep the analysis prompt explicit about the JSON shape and Japanese-friendly labels, but constrain the schema via `response_schema`.


### Phase 4 — HTTP wiring


Add use-case provider functions to `app/dependencies.py` that assemble use cases from the existing adapter providers, and make `get_task_queue()` mode-aware:

    def get_task_queue() -> TaskQueuePort:
        s = get_settings()
        if s.task_queue_mode == "cloud_tasks" and s.google_cloud_project:
            return CloudTasksAdapter()
        return LocalHttpTaskQueueAdapter()

Rewrite `app/handlers/closet_routes.py` so each route is authenticated and delegates to its use case, translating domain errors to HTTP status codes:

- `GET /closet/upload-url?item_id=...` → `Depends(verify_firebase_token)`, call `GetUploadUrlUseCase`; `MaxClosetItemsExceeded` → 429; return `{upload_url, item_id}`.
- `POST /closet/items/{item_id}/complete` → auth, `RegisterClothingItemUseCase`; return `{item_id, status: "PROCESSING"}`.
- `DELETE /closet/items/{item_id}` → auth, `DeleteClosetItemUseCase`; `ClosetItemNotFound` → 404; return `204 No Content`.

Create `app/handlers/internal_routes.py` with `POST /internal/tasks/process-upload` that reads `{userId, item_id}` and calls `ProcessUploadedClothingItemUseCase`. This route is **not** behind `verify_firebase_token` (it is an internal queue target; in production it is protected by Cloud Run OIDC / private networking per §10.3 — out of scope here, note it). Register the router in `app/main.py` (no prefix, so the path is exactly `/internal/tasks/process-upload`). In the `startup` handler, call `ElasticsearchEmbeddingRepository().ensure_index()` so the index exists before the first write. Remove the obsolete 501 stubs and any now-unused imports.


### Phase 5 — Tests and validation


Unit tests (no network): add in-memory fakes implementing each port (a dict-backed `FakeClosetRepo`, `FakeImageStorage`, `FakeEmbeddingSearch`, `FakeTaskQueue`, `FakeGemini`) under `tests/use_cases/`. Cover: upload-url under and over the cap (429), register writes a PROCESSING item and enqueues exactly one job, process flips to READY and indexes, process sets ERROR and re-raises on analysis failure, delete is best-effort and 404s on a missing item. Add an adapter test for `ElasticsearchEmbeddingRepository.ensure_index`/`index_item`/`delete_item` against the Docker ES (guard with a skip if `localhost:9200` is unreachable). Then run the local end-to-end script in *Concrete Steps* and confirm the three-store outcome.


## Concrete Steps


### Working directory


Unless stated otherwise, run commands from `/Users/ran/my-app/gen-fashion`.


### Step 1 — Add dependencies


Edit `fastapi-service/requirements.txt` and `fastapi-service/pyproject.toml` to add `boto3`, `google-genai`, `google-cloud-firestore` (pins in Phase 0). Then:

    cd /Users/ran/my-app/gen-fashion/fastapi-service
    python -m pip install -r requirements.txt

Expected: install completes with no dependency-resolution error. If pip reports a conflict on `google-cloud-firestore`, drop the explicit pin and rely on `firebase-admin`'s transitive version; record this in Surprises.


### Step 2 — Add MinIO to the local stack


In `docker-compose.yml`, add a service (S3-compatible local storage):

    minio:
      image: minio/minio:latest
      command: server /data --console-address ":9001"
      environment:
        - MINIO_ROOT_USER=minioadmin
        - MINIO_ROOT_PASSWORD=minioadmin
      ports:
        - "9000:9000"
        - "9001:9001"
      healthcheck:
        test: ["CMD", "mc", "ready", "local"]
        interval: 10s
        timeout: 5s
        retries: 5

Add MinIO env to the `fastapi-service` block and set the spec-aligned vars (also mirror these in root `.env.example`):

    - ELASTICSEARCH_URL=http://elasticsearch:9200
    - GOOGLE_CLOUD_PROJECT=gen-fashion-local
    - MAX_CLOSET_IMAGES_PER_USER=20
    - GOOGLE_GENAI_USE_VERTEXAI=false
    - GEMINI_API_KEY=${GEMINI_API_KEY:-dummy-key}
    - R2_ENDPOINT_URL=http://minio:9000
    - R2_ACCESS_KEY_ID=minioadmin
    - R2_SECRET_ACCESS_KEY=minioadmin
    - R2_BUCKET_NAME=gen-fashion-images
    - TASK_QUEUE_MODE=local
    - ADK_INTERNAL_BASE_URL=http://fastapi-service:8000

Then start the stack:

    cd /Users/ran/my-app/gen-fashion
    make dev

Expected: `elasticsearch`, `firestore-emulator`, `minio`, `fastapi-service` come up healthy. `http://localhost:8000/health` returns `{"status":"ok"}`.


### Step 3 — Create the bucket and CORS (one-time, local)


With MinIO running, create the bucket and CORS rule (use the `mc` client or a short boto3 snippet). Example with `mc`:

    docker run --rm --network gen-fashion_default --entrypoint sh minio/mc -c "\
      mc alias set local http://minio:9000 minioadmin minioadmin && \
      mc mb -p local/gen-fashion-images"

Apply a CORS policy allowing `PUT, GET, OPTIONS` from the Flutter dev origin (the §8.4 rule). For R2/staging, set the equivalent CORS rule in the Cloudflare dashboard or via `put_bucket_cors`. Confirm the bucket exists (`mc ls local/`).


### Step 4 — Implement Phases 0–4


Make the edits described in *Plan of Work* (domain fields, `app/config.py`, `app/auth.py`, the four adapters + `local_task_queue.py`, the `GeminiAnalysisPort`/adapter, the four use cases, the route rewrites, the internal router, and the `startup` `ensure_index()` call). After each adapter or use case, run `pytest` to keep the suite green:

    cd /Users/ran/my-app/gen-fashion/fastapi-service
    python -m pytest -q

Expected: existing domain/health tests keep passing; new use-case tests pass as you add them.


### Step 5 — Local end-to-end smoke test


With `make dev` up and Phase 1's test override or `FIREBASE_AUTH_EMULATOR_HOST` configured, exercise the full path. Outline (adapt token handling to the chosen local auth approach):

    # 1. Ask for an upload URL (item_id generated client-side)
    ITEM_ID=$(python -c "import uuid;print(uuid.uuid4())")
    curl -s "http://localhost:8000/closet/upload-url?item_id=$ITEM_ID" \
      -H "Authorization: Bearer $TOKEN"
    # -> {"upload_url":"http://localhost:9000/gen-fashion-images/<uid>/closet/<id>.jpg?...","item_id":"<id>"}

    # 2. PUT the bytes straight to storage using the signed URL
    curl -s -X PUT --upload-file sample.jpg -H "Content-Type: image/jpeg" "$UPLOAD_URL"

    # 3. Tell the API the upload finished (writes PROCESSING + enqueues worker)
    curl -s -X POST "http://localhost:8000/closet/items/$ITEM_ID/complete" \
      -H "Authorization: Bearer $TOKEN"
    # -> {"item_id":"<id>","status":"PROCESSING"}

    # (LocalHttpTaskQueueAdapter calls /internal/tasks/process-upload synchronously)

    # 4. Confirm Firestore shows READY (emulator REST API or a tiny python client read)
    # 5. Confirm Elasticsearch has the doc
    curl -s "http://localhost:9200/clothing_items/_doc/$ITEM_ID"

    # 6. Delete and confirm removal from all three stores
    curl -s -X DELETE "http://localhost:8000/closet/items/$ITEM_ID" \
      -H "Authorization: Bearer $TOKEN" -o /dev/null -w "%{http_code}\n"   # -> 204

If `GEMINI_API_KEY` is a dummy value, analysis/embedding will fail; supply a real developer key to see `status: "READY"`, or assert the documented `ERROR` path. Record the run in Artifacts.


## Validation and Acceptance


Acceptance is the M2 backend exit behavior, observed end to end:

- **M2-2:** A request to `GET /closet/upload-url` without a valid `Authorization: Bearer` token returns `401`; with a valid token it returns `200`.
- **M2-3:** With the user at or above `MAX_CLOSET_IMAGES_PER_USER` items, `GET /closet/upload-url` returns `429`; otherwise it returns a signed URL whose host is the configured storage endpoint and whose key is `{uid}/closet/{itemId}.jpg`.
- **M2-7:** A `PUT` to the signed URL stores the object; `verify_image_exists` returns `True` afterward; `get_image_bytes` returns the uploaded bytes.
- **M2-4 + M2-8 + M2-10:** `POST /closet/items/{id}/complete` creates `users/{uid}/closet/{id}` with `status: "PROCESSING"` and enqueues exactly one job.
- **M2-5 + M2-9:** After the worker runs, the Firestore document reads `status: "READY"` with populated `category`, `tags`, `season`, `colors`, `embeddingId`, and `clothing_items/_doc/{id}` exists in Elasticsearch with matching keyword fields.
- **M2-6:** `DELETE /closet/items/{id}` returns `204` and the item is gone from Firestore, Elasticsearch, and storage; deleting a missing item returns `404`.
- **Suite:** `python -m pytest -q` in `fastapi-service` passes, including the new use-case unit tests and the ES adapter test (skipped only if `localhost:9200` is unreachable).

Flip each matrix row to ✅ only when its specific item above is demonstrated. Until then it stays 🟡.


## Idempotence and Recovery


- `ensure_index()` is a create-if-absent and is safe to call on every startup.
- `index_item` is an upsert keyed by `item_id`; re-running the worker overwrites rather than duplicates. Firestore writes use the deterministic `{uid}/closet/{itemId}` path, so a retried `complete` or worker run is idempotent.
- The worker is safe to retry: it re-fetches bytes, re-analyzes, and re-writes. Cloud Tasks (or the local adapter on a manual re-POST) can replay a job; the terminal state is the same.
- Recovery from a stuck `PROCESSING` item: re-POST the job payload to `/internal/tasks/process-upload`; if analysis keeps failing, the document lands in `ERROR` and the item can be deleted via the API.
- Recovery from a missing local bucket: re-run Step 3 (`mc mb -p` is idempotent).
- `make clean` tears the stack down (`docker-compose down -v`), discarding MinIO/ES/Firestore local data; re-run `make dev` + Step 3 to rebuild.


## Artifacts and Notes


(To be filled during execution.) Capture: the end-to-end smoke-test transcript from Step 5 showing `PROCESSING`→`READY` and the `204` delete; one example Firestore document and the matching Elasticsearch `_doc`; the resolved `google-genai` embedding call (model id, dimensionality, whether image-embedding worked or the keyword-only fallback was used); and `pytest -q` output.


## Interfaces and Dependencies


- **`boto3`** (new) — S3-compatible client for Cloudflare R2 and the local MinIO stand-in: presigned PUT/GET URLs, `put/get/head/delete_object`. Needed for M2-7 and the worker's byte fetch.
- **`google-genai`** (new) — Gemini client for image analysis (structured output, M2-5/§6.1) and embedding generation (§8.3). Local dev authenticates with `GEMINI_API_KEY` (developer API); production sets `GOOGLE_GENAI_USE_VERTEXAI=true` and uses ADC (§12.2). **Open item:** the exact `gemini-embedding-2` call that embeds *image bytes* at `output_dimensionality=768` is unverified in this repo. §8.3 asserts image+text share one vector space; the M1 plan only exercised text/agent paths. The worker treats embedding as best-effort and proceeds without a vector on failure (Decision Log), so M2 acceptance does not depend on resolving this; it must be confirmed before M5-5 vector search.
- **`google-cloud-firestore`** (made explicit) — `AsyncClient` for the closet repository (M2-8). Honors `FIRESTORE_EMULATOR_HOST` locally; uses ADC in production.
- **`elasticsearch==8.11.0`** (present) — `AsyncElasticsearch` for the `clothing_items` index (M2-9). Local Docker ES from `make dev`; GCE-hosted ES is deferred (M1-3).
- **`firebase-admin==6.2.0`** (present) — `auth.verify_id_token` for the middleware (M2-2).
- **`google-cloud-tasks==2.14.0`** (present) — `CloudTasksAdapter` enqueue in production (M2-10); the local adapter uses `httpx` (present) instead.
- **`pydantic-settings`** (present) — central `Settings` in `app/config.py`.
- **Ports touched:** `EmbeddingSearchPort.index_item` widens to carry the index document (Decision Log); a new `GeminiAnalysisPort` is added; `ImageStoragePort` gains `get_image_bytes`. All other ports keep their M0 signatures.
- **Out of this plan:** M2-1 (Flutter Google Sign-In), M2-11 (Flutter closet UI), M2-12 (Firebase Security Rules), and all M3–M6 work. Vector/hybrid search and GCE-hosted Elasticsearch remain deferred per the M1-3 decision.
