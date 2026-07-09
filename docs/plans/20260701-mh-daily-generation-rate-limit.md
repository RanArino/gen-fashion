# MH — Daily Image Generation Rate Limit (Production)


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Image generation via Nano Banana (`gemini-2.5-flash-image`) on Vertex AI incurs real billing cost per call. With no limit, a single user could exhaust the project quota or run up significant spend in one session. This change adds a **daily per-user generation limit** (default: 5 completed generations per UTC calendar day) that is active in both local Docker and production. The first enforcement point is `POST /sessions/{id}/source`, before any propose/search ADK run starts; `POST /sessions/{id}/select` remains a second guard before the generate ADK run.

After this change:
- A user who has already completed 5 image generations today gets HTTP 429 on the `/source` call before ADK launch. Existing `PROPOSING` sessions also get HTTP 429 on `/select` before generate launch. Their previous sessions are unaffected.
- Users who have completed fewer than 5 receive no change in behavior.
- Local `make dev` uses the same default limit (`5`) so the quota behavior is testable locally.
- The limit is controlled by a single env var `MAX_DAILY_GENERATIONS_PER_USER`; set it to `0` only when intentionally disabling the threshold.


## Progress


- [x] (2026-06-30 23:31Z) Milestone A — Backend enforcement: config, exception, port method, adapter query, use-case check, handler 429, tests.
- [x] (2026-06-30 23:38Z) Milestone B — Deployment wiring: `deploy_fastapi.sh` + `.env.example`, Cloud Run redeploy, env/health smoke.
- [x] (2026-07-01 13:03Z) Local hardening — moved the first quota check to `SelectClothingSourceUseCase` before `phase="propose"` ADK launch, kept `SelectCandidatesUseCase` as a second guard, enabled local Docker/`.env.example` default `5`, and verified FastAPI/container tests.


## Surprises & Discoveries


- Observation: The local default `python3` is 3.14, which cannot build the pinned `pydantic-core==2.14.1`.
  Evidence: `python3 -m venv .venv && pip install -r requirements.txt` failed while building `pydantic-core` with `ForwardRef._evaluate() missing 1 required keyword-only argument: 'recursive_guard'`. Retried with `/opt/homebrew/bin/python3.12`, and the test suite passed.

- Observation: Production Cloud Run did not previously have `MAX_DAILY_GENERATIONS_PER_USER` set.
  Evidence: `gcloud run services describe fastapi-service --project your-project-id --region asia-northeast1` before redeploy showed no env var with that name; after redeploy, the filtered env output was `[{'name': 'MAX_DAILY_GENERATIONS_PER_USER', 'value': '5'}]`.

- Observation: Enforcing only at `/select` is too late for cost control.
  Evidence: the user could reach the 6th run's `PROPOSING` screen and only then receive 429 before image selection; the propose ADK run and Elasticsearch search had already happened. The first check now runs in `SelectClothingSourceUseCase` before `AgentRunPort.start_session_run(phase="propose")`.


## Decision Log


- Decision: Use `max_daily_generations_per_user: int = 0` where `0` means unlimited, but configure local Docker and production to `5` by default.
  Rationale: Mirrors the existing `MAX_CLOSET_IMAGES_PER_USER` convention already in `config.py` while keeping the real quota behavior testable locally. Zero remains available only as an intentional disable switch.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Enforce the limit first in `SelectClothingSourceUseCase.execute()` and again in `SelectCandidatesUseCase.execute()`, not in the HTTP handler.
  Rationale: `/source` is the earliest point before the propose ADK run and Elasticsearch search. `/select` remains necessary as a second guard for already-open `PROPOSING` sessions and concurrent flows. Placing both checks in use cases keeps the rule in the business logic layer and makes it testable without HTTP.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Count "today" as UTC calendar day (midnight UTC to midnight UTC).
  Rationale: Firestore stores `completedAt` in UTC. The query `completedAt >= today_utc_midnight` is a single range inequality, which Firestore handles efficiently with the existing composite index. This also means the limit resets at 09:00 JST — a reasonable time for the Japan-primary audience.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Rely on the existing `(userId, status, completedAt DESC)` Firestore composite index for the count query.
  Rationale: The new query (`userId ==, status ==, completedAt >=, limit(max+1)`) uses the same three fields already in the composite index. Firestore can satisfy a `>=` range filter using a descending index. No new index entry is required unless Firestore rejects the query at runtime and logs a link to create one (see Idempotence & Recovery for fallback).
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Read at most `max_daily + 1` documents when counting.
  Rationale: We only need to know whether `count >= limit`; reading more than `limit + 1` is wasteful. With the default limit of 5, each quota check reads at most 6 Firestore documents. This is negligible cost.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Count only `COMPLETED` sessions, not `ERROR` / `TIMEOUT` / in-flight sessions.
  Rationale: A failed generation does not produce a usable image; charging it against the daily limit would penalize users for system errors or network failures they did not cause. Edge case: if SSE disconnects mid-stream but `adk-agent-service` finishes in the background and writes `status=COMPLETED` + `completedAt`, the session IS counted. This is intentional — the image exists in R2 and will appear in the History gallery even if Flutter never displayed it live. The user consumed a Vertex AI generation call.
  Date/Author: 2026-07-01 / Ran

- Decision: Architecture-overview.md does not need updating.
  Rationale: This change adds a new method to the existing `StylingRepositoryPort` and checks inside existing session use cases. No new component, port/adapter, data store, or external service is added. The boundary between implemented and planned code does not change structurally.
  Date/Author: 2026-07-01 / ExecPlan


## Outcomes & Retrospective


Implemented and deployed.

Backend enforcement now runs in `SelectClothingSourceUseCase.execute()` before `session.select_source(...)` and before `AgentRunPort.start_session_run(phase="propose")`. The same check also remains in `SelectCandidatesUseCase.execute()` before `session.select_candidates(...)` and before `AgentRunPort.start_session_run(phase="generate")`. `MAX_DAILY_GENERATIONS_PER_USER=0` skips the Firestore count entirely; positive values query completed sessions since UTC midnight and raise `DailyGenerationLimitExceeded` when `count >= limit`. Both route handlers map that exception to HTTP 429.

Deployment/local wiring is in place: `.env.example` and `docker-compose.yml` default local development to `MAX_DAILY_GENERATIONS_PER_USER=5`, and `scripts/deploy/deploy_fastapi.sh` sets `MAX_DAILY_GENERATIONS_PER_USER=5` for Cloud Run. Cloud Build pushed `asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion/fastapi-service:mh-20260701-083153`; Cloud Run revision `fastapi-service-00015-f48` is serving 100% traffic. Local container `/health` returns `{"status":"ok"}` and reads `max_daily_generations_per_user=5`.

The exact authenticated 429 production smoke after real completed generations was not run, because it would require creating paid Vertex AI generations. The behavior is covered by use-case and route tests, and the live service has the production env var set.


## Context and Orientation


The gen-fashion app uses a hexagonal architecture split across two Cloud Run containers:

- `fastapi-service` — REST API; handles authentication and all client-facing endpoints.
- `adk-agent-service` — ADK agent runner; performs search and image generation.

The first paid-risk workflow begins when the user calls `POST /sessions/{id}/source`. This is where the propose ADK run can start and search Elasticsearch, so the daily cap is checked before that run is launched:

    session_routes.py → select_source handler
      → SelectClothingSourceUseCase.execute()
        → enforce_daily_generation_limit(...)
        → styling_repo.update(session)            (write source/preference, transition to SEARCHING)
        → agent_run.start_session_run(phase="propose")  ← ADK searches/proposes here

The cap is checked again when the user calls `POST /sessions/{id}/select` after the agent pauses at `PROPOSING` state:

    session_routes.py → select_candidates handler
      → SelectCandidatesUseCase.execute()
        → enforce_daily_generation_limit(...)
        → styling_repo.update(session)            (write selectedItems, transition to GENERATING)
        → agent_run.start_session_run(phase="generate")  ← ADK runs style_synthesizer here

The generation count is tracked by querying the `sessions` Firestore collection:

    sessions/{sessionId}
      userId: string
      status: "COMPLETED" | "PROPOSING" | ...
      completedAt: timestamp    ← set by adk-agent-service when session reaches COMPLETED

The existing `StylingRepositoryPort` in `fastapi-service/app/ports/styling_repository.py` is the abstract interface; its concrete implementation is `FirestoreStylingRepository` in `fastapi-service/app/adapters/firestore_styling_repo.py`.

The existing `MAX_CLOSET_IMAGES_PER_USER` limit in `GetUploadUrlUseCase` (→ HTTP 429) is the pattern this change mirrors.


## Plan of Work


### Milestone A — Backend enforcement


**A-1: config** (`fastapi-service/app/config.py`)

Add one field after `max_closet_images_per_user`:

    max_daily_generations_per_user: int = 0

Zero means unlimited. Pydantic-settings will read `MAX_DAILY_GENERATIONS_PER_USER` from the environment automatically.


**A-2: exception** (`fastapi-service/app/domain/styling/exceptions.py`)

Add one exception class at the bottom of the file:

    class DailyGenerationLimitExceeded(StylingException):
        """Raised when the user has reached the daily image generation limit."""
        pass


**A-3: port method** (`fastapi-service/app/ports/styling_repository.py`)

Add one abstract method. Import `datetime` from the standard library at the top of the file, then add:

    @abstractmethod
    async def count_completed_today(self, user_id: str, since: datetime) -> int:
        """Return the number of COMPLETED sessions for user_id whose completedAt >= since."""
        raise NotImplementedError


**A-4: Firestore adapter** (`fastapi-service/app/adapters/firestore_styling_repo.py`)

Implement the new method. Import `datetime` at the top of the file (alongside the existing imports), then add after the `delete` method:

    async def count_completed_today(self, user_id: str, since: datetime) -> int:
        settings = get_settings()
        cap = max(settings.max_daily_generations_per_user + 1, 2)
        query = (
            self._collection()
            .where("userId", "==", user_id)
            .where("status", "==", StyleSessionState.COMPLETED.value)
            .where("completedAt", ">=", since)
            .limit(cap)
        )
        count = 0
        async for _ in query.stream():
            count += 1
        return count

The `cap` is `max_daily_generations_per_user + 1` so the query reads no more than 6 documents for the default limit of 5. The `max(..., 2)` guard prevents a zero cap when the limit is `0` (which should never reach this path, but is safe).


**A-5: use-case enforcement** (`fastapi-service/app/use_cases/styling/select_source.py`, `fastapi-service/app/use_cases/styling/select_candidates.py`)

Inject `Settings` and check the limit before triggering either agent run. The current implementation factors the shared logic into `fastapi-service/app/use_cases/styling/daily_generation_limit.py`.

Add imports:

    from datetime import datetime, timezone
    from app.config import Settings, get_settings
    from app.domain.styling.exceptions import DailyGenerationLimitExceeded

Change the constructor signature:

    def __init__(
        self,
        styling_repo: StylingRepositoryPort,
        agent_run: AgentRunPort,
        settings: Settings | None = None,
    ):
        self.styling_repo = styling_repo
        self.agent_run = agent_run
        self._settings = settings or get_settings()

In `SelectClothingSourceUseCase.execute()`, after source/session validation and before `session.select_source(...)`, call the shared limit helper. In `SelectCandidatesUseCase.execute()`, after candidate validation and before `session.select_candidates(selected)`, call the same helper.

The helper implements:

    if self._settings.max_daily_generations_per_user > 0:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        count = await self.styling_repo.count_completed_today(user_id, today_start)
        if count >= self._settings.max_daily_generations_per_user:
            raise DailyGenerationLimitExceeded(
                f"Daily generation limit of "
                f"{self._settings.max_daily_generations_per_user} reached. "
                f"Limit resets at midnight UTC."
            )


**A-6: dependency wiring** (`fastapi-service/app/dependencies.py`)

Pass `get_settings()` to both session use cases:

    def get_select_source_use_case() -> SelectClothingSourceUseCase:
        return SelectClothingSourceUseCase(
            get_styling_repository(),
            get_closet_repository(),
            get_agent_run(),
            get_settings(),
        )

    def get_select_candidates_use_case() -> SelectCandidatesUseCase:
        return SelectCandidatesUseCase(get_styling_repository(), get_agent_run(), get_settings())


**A-7: route handler** (`fastapi-service/app/handlers/session_routes.py`)

Import the new exception at the top:

    from app.domain.styling.exceptions import DailyGenerationLimitExceeded

In both `select_source` and `select_candidates`, add a catch clause before the `AgentRunStartFailed` catch:

    except DailyGenerationLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


**A-8: tests**

Add to `fastapi-service/tests/use_cases/test_styling_use_cases.py` (or create a focused test file for the rate limit):

- A test that configures `max_daily_generations_per_user=5`, stubs `count_completed_today` to return `5`, and asserts `DailyGenerationLimitExceeded` is raised by `execute()`.
- A test that stubs `count_completed_today` to return `4` and asserts the execution proceeds normally (no exception).
- A test that sets `max_daily_generations_per_user=0` (unlimited), stubs `count_completed_today` to return `99`, and asserts no exception is raised (count method is not called at all).

Add to `fastapi-service/tests/test_session_routes.py`:

- A test that mocks `SelectCandidatesUseCase.execute()` to raise `DailyGenerationLimitExceeded` and asserts the endpoint returns HTTP 429.


### Milestone B — Deployment wiring


**B-1: `.env.example`** (repo root `gen-fashion/.env.example`)

Add after the `MAX_CLOSET_IMAGES_PER_USER` line:

    # 5 enables local quota testing. Set to 0 only when intentionally disabling the limit.
    MAX_DAILY_GENERATIONS_PER_USER=5


**B-2: deploy script** (`scripts/deploy/deploy_fastapi.sh`)

Add one line to the `ENV_VARS` block (before the OIDC conditional block):

    ENV_VARS+="|MAX_DAILY_GENERATIONS_PER_USER=5"


**B-3: Cloud Run redeploy**

Run the deploy script (second-pass form, with `--fastapi-url` already known):

    FASTAPI_URL=$(gcloud run services describe fastapi-service \
      --project your-project-id --region asia-northeast1 --format='value(status.url)')

    bash scripts/deploy/deploy_fastapi.sh \
      --project your-project-id \
      --region asia-northeast1 \
      --image <current-image-tag> \
      --adk-url <adk-service-url> \
      --fastapi-url "$FASTAPI_URL" \
      --es-internal-ip <es-internal-ip> \
      --r2-endpoint-url <...> \
      --r2-public-endpoint-url <...> \
      --r2-bucket-name gen-fashion-images

After deploy, verify the env var is present:

    gcloud run services describe fastapi-service \
      --project your-project-id --region asia-northeast1 \
      --format='value(spec.template.spec.containers[0].env)'

Confirm `MAX_DAILY_GENERATIONS_PER_USER=5` appears in the output.


## Concrete Steps


Working directory: `/Users/ran/my-app/gen-fashion`

Step 1 — Edit `fastapi-service/app/config.py`: add `max_daily_generations_per_user: int = 0` after `max_closet_images_per_user`.

Step 2 — Edit `fastapi-service/app/domain/styling/exceptions.py`: add `DailyGenerationLimitExceeded`.

Step 3 — Edit `fastapi-service/app/ports/styling_repository.py`: add `from datetime import datetime` import and abstract `count_completed_today` method.

Step 4 — Edit `fastapi-service/app/adapters/firestore_styling_repo.py`: add `from datetime import datetime` to imports, add `count_completed_today` implementation at the bottom of the class.

Step 5 — Edit `fastapi-service/app/use_cases/styling/daily_generation_limit.py`, `select_source.py`, and `select_candidates.py`: add shared limit helper, inject settings, and check before each agent run.

Step 6 — Edit `fastapi-service/app/dependencies.py`: pass `get_settings()` to `SelectClothingSourceUseCase(...)` and `SelectCandidatesUseCase(...)`.

Step 7 — Edit `fastapi-service/app/handlers/session_routes.py`: import `DailyGenerationLimitExceeded`, add 429 catch in `select_source` and `select_candidates`.

Step 8 — Write/extend tests in `fastapi-service/tests/`.

Step 9 — Run tests:

    cd fastapi-service
    /opt/homebrew/bin/python3.12 -m venv .venv312
    .venv312/bin/pip install -q -r requirements.txt
    .venv312/bin/pytest -q

Observed after local hardening: 76 passed.

Step 10 — Edit `.env.example`: set `MAX_DAILY_GENERATIONS_PER_USER=5` for local quota testing.

Step 11 — Edit `scripts/deploy/deploy_fastapi.sh`: add `ENV_VARS+="|MAX_DAILY_GENERATIONS_PER_USER=5"`.

Step 12 — Build and push updated `fastapi-service` image; run deploy script (Milestone B-3 above). Completed with image `asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion/fastapi-service:mh-20260701-083153` and revision `fastapi-service-00015-f48`.

Step 13 — Smoke test production limit:

    # Sign in and get a Firebase ID token (use the browser or scripts/m5_coordination_smoke.py helper)
    # After 5 completed sessions, the next POST /sessions/{id}/source must return 429
    # before ADK launch. Existing PROPOSING sessions must also get 429 on /select.
    # Alternatively: set MAX_DAILY_GENERATIONS_PER_USER=1 temporarily, complete one session,
    # then verify the next /source and /select return 429.


## Validation and Acceptance


### Local (automated)

    cd fastapi-service
    .venv312/bin/pytest -q

Observed after local hardening: 76 passed. Tests exercise:
- `DailyGenerationLimitExceeded` raised when `count >= limit` and `limit > 0`.
- No exception raised when `limit == 0` (unlimited mode; `count_completed_today` is never called).
- `SelectClothingSourceUseCase` leaves the session in `SOURCE_SELECTING` and does not call `agent_run.start_session_run(...)` when the limit is reached.
- HTTP 429 with `DailyGenerationLimitExceeded` detail returned by both route handlers.

### Production (deployment smoke)

Condition: `MAX_DAILY_GENERATIONS_PER_USER=5` is set on the Cloud Run service (confirmed via `gcloud run services describe`).

Observed:
- `gcloud run services describe fastapi-service --project your-project-id --region asia-northeast1 --format='value(status.url,status.latestReadyRevisionName,spec.template.spec.containers[0].image)'` returned `https://fastapi-service-hvwhpzcehq-an.a.run.app`, `fastapi-service-00015-f48`, and `asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion/fastapi-service:mh-20260701-083153`.
- Filtering the live env returned `MAX_DAILY_GENERATIONS_PER_USER=5`.
- `curl -fsS "$FASTAPI_URL/health"` returned `{"status":"ok"}`.

Not run:
- The exact paid-flow 429 smoke after 5 completed production generations was not run to avoid spending Vertex AI generation calls solely for verification.

Expected behavior:
- A user who completes their 5th generation today can still see the result.
- The same user's next `POST /sessions/{id}/source` returns HTTP `429 Too Many Requests` before ADK launch, with a JSON body containing `"Daily generation limit of 5 reached. Limit resets at midnight UTC."`.
- If the user already has a `PROPOSING` session, the next `POST /sessions/{id}/select` also returns the same HTTP 429 before the generate agent run.
- A different user who has 0 completions today is unaffected.
- The next UTC calendar day, the first user's limit is cleared (no code change; the query window shifts forward).


## Idempotence and Recovery


All code edits are non-destructive and individually reversible. No database migration is required. Setting `MAX_DAILY_GENERATIONS_PER_USER=0` on Cloud Run at any time disables the limit immediately.

If the Firestore `count_completed_today` query fails at runtime with a missing-index error, Firestore logs a URL to create the required index. Add the following entry to `firestore.indexes.json` and redeploy:

    {
      "collectionGroup": "sessions",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "userId", "order": "ASCENDING" },
        { "fieldPath": "status", "order": "ASCENDING" },
        { "fieldPath": "completedAt", "order": "ASCENDING" }
      ]
    }

Then deploy it with:

    firebase deploy --only firestore:indexes --project your-project-id


## Artifacts and Notes


Files touched:

    fastapi-service/app/config.py
    fastapi-service/app/domain/styling/exceptions.py
    fastapi-service/app/ports/styling_repository.py
    fastapi-service/app/adapters/firestore_styling_repo.py
    fastapi-service/app/use_cases/styling/daily_generation_limit.py
    fastapi-service/app/use_cases/styling/select_source.py
    fastapi-service/app/use_cases/styling/select_candidates.py
    fastapi-service/app/dependencies.py
    fastapi-service/app/handlers/session_routes.py
    fastapi-service/tests/use_cases/test_styling_use_cases.py  (extend)
    fastapi-service/tests/test_session_routes.py                (extend)
    .env.example
    scripts/deploy/deploy_fastapi.sh

Verification artifacts:

    cd fastapi-service
    pytest -q
    # 76 passed

    docker-compose exec -T fastapi-service python -m pytest -q \
      tests/use_cases/test_styling_use_cases.py::test_select_source_rejects_when_daily_generation_limit_reached_before_agent_run \
      tests/test_session_routes.py::test_select_source_returns_429_when_daily_generation_limit_reached
    # 2 passed

    gcloud builds submit fastapi-service --tag asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion/fastapi-service:mh-20260701-083153 --project your-project-id
    # Build 43eec9cd-a686-41e3-bcf8-70e261280292 SUCCESS

    bash scripts/deploy/deploy_fastapi.sh ... --image asia-northeast1-docker.pkg.dev/your-project-id/gen-fashion/fastapi-service:mh-20260701-083153 ...
    # Service [fastapi-service] revision [fastapi-service-00015-f48] has been deployed and is serving 100 percent of traffic.

    curl -fsS "$FASTAPI_URL/health"
    # {"status":"ok"}

`adk-agent-service` is not touched — it executes generation but never decides whether to permit it.

Flutter client note: the current error handling for `/source` and `/select` displays a generic error on non-202 responses. A 429 will surface as a generic error to the user in the current Flutter code. A follow-up improvement would catch 429 specifically and show "今日の生成上限（5回）に達しました。明日またお試しください。" but that Flutter UX change is out of scope for this ExecPlan.


## Interfaces and Dependencies


| Name | Location | Purpose |
|---|---|---|
| `Settings.max_daily_generations_per_user` | `fastapi-service/app/config.py` | Configurable limit; `0` = unlimited |
| `DailyGenerationLimitExceeded` | `fastapi-service/app/domain/styling/exceptions.py` | Domain exception; caught by route handler → HTTP 429 |
| `StylingRepositoryPort.count_completed_today` | `fastapi-service/app/ports/styling_repository.py` | Abstract port method returning today's completed generation count |
| `FirestoreStylingRepository.count_completed_today` | `fastapi-service/app/adapters/firestore_styling_repo.py` | Firestore query: `userId==, status==COMPLETED, completedAt >= today_utc_start, limit(cap)` |
| `SelectClothingSourceUseCase` | `fastapi-service/app/use_cases/styling/select_source.py` | First enforcement point; raises `DailyGenerationLimitExceeded` before triggering the propose/search agent run |
| `SelectCandidatesUseCase` | `fastapi-service/app/use_cases/styling/select_candidates.py` | Second enforcement point; raises `DailyGenerationLimitExceeded` before triggering the generate agent run |
| `select_source` / `select_candidates` route handlers | `fastapi-service/app/handlers/session_routes.py` | Map `DailyGenerationLimitExceeded` → HTTP 429 |
| `deploy_fastapi.sh` | `scripts/deploy/deploy_fastapi.sh` | Passes `MAX_DAILY_GENERATIONS_PER_USER=5` to Cloud Run in production |
