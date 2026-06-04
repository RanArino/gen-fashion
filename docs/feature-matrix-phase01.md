# Phase 1 Feature Matrix — gen-fashion

> **Last updated:** 2026-06-04
> **Source of truth:** [req-phase01.md](req-phase01.md) — this matrix tracks **implementation status** of the requirements defined there. Every feature row links back to the relevant section / Use Case of `req-phase01.md`.
> **Scope:** Phase 1 MVP (Hackathon). Phase 1a (Web GUI) is implemented first; Phase 1b (LINE) follows.

---

## How to use this document

This file is the **implementation tracker** for Phase 1. `req-phase01.md` defines *what* to build; this file tracks *how far each piece is*.

### Status legend

| Status | Meaning |
|---|---|
| ✅ Implemented | Feature is fully implemented and works as specified in `req-phase01.md`. |
| 🟡 In progress | Feature is actively being developed, under review, or has an approved ExecPlan in flight. |
| ❌ Not yet implemented | Feature is not yet implemented; no functionality exists. |

### Maintenance rules (keep this file synced)

1. **This file must stay synced with `req-phase01.md`.** If a requirement is added, removed, or re-scoped in `req-phase01.md`, update the matching row here in the same change.
2. **Status transitions are mandatory.** Whenever work on a tracked requirement *starts*, is *planned via an ExecPlan*, or is *completed*, update its status here.
3. **ExecPlan rule:** If an ExecPlan targets a requirement currently marked `❌ Not yet implemented`, that requirement **must be changed to `🟡 In progress` in the same change as the plan**.
4. **Completion rule:** Only mark `✅ Implemented` once the feature works end-to-end as specified — not when code merely exists.

---

## Milestone overview

Implementation proceeds **milestone by milestone**, in order. Each milestone is independently demoable and unblocks the next.

| Milestone | Title | Phase | Depends on | Goal |
|---|---|---|---|---|
| **M0** | Project Foundation & Local Dev Environment | 1a | — | Repo skeleton, hexagonal layout, local dev stack reproducible by any teammate. |
| **M1** | PoC & Infrastructure Validation | 1a | M0 | De-risk the 3 "Early PoC required" items before feature work commits to them. |
| **M2** | Auth & Closet Management (Web) | 1a | M0, M1 | Logged-in users upload/manage closet images; embedding pipeline runs. |
| **M3** | Shared Demo Closet | 1a | M2 | First-time users can try the app without uploading clothes. |
| **M4** | ADK Agents Core | 1a | M1, M2 | Orchestrator + sub-agents run their tools locally on ADK Web UI. |
| **M5** | Coordination Flow & Accordion UI (Web E2E) | 1a | M3, M4 | Full Web GUI flow: session → analysis → search → propose → generate, with live Accordion UI. |
| **M6** | LINE Channel Integration | 1b | M5 | LINE users get the full coordination experience; Rakuten search added. |

> Phase 1a = **M0–M5**. Phase 1b = **M6**. LINE work (M6) must not start until M5 is complete (`req-phase01.md` §14).

---

## M0 — Project Foundation & Local Dev Environment

**Scope:** Establish the codebase structure and a reproducible local development environment. No business features yet. Reference: `req-phase01.md` §3, §4, §5, §9.4, ADL-017.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M0-1 | Hexagonal/DDD project skeleton | ✅ Implemented | Directory layout for Closet & Styling bounded contexts: domain (aggregates, VOs), ports, adapters, use cases. No logic, structure only. | §3, §4 |
| M0-2 | Domain model — Closet Context | ✅ Implemented | `ClothingItem` (Aggregate Root), `ClothingItemId`, `ClothingTag`, `ImageEmbedding` value objects with invariants. | §4.2, §4.3 |
| M0-3 | Domain model — Styling Context | ✅ Implemented | `StyleSession` (Aggregate Root + state machine), `StyleSessionId`, `CoordinateProposal`, `UserPreference`, `StyleResult`, `ClothingSource` enum. | §4.2, §4.3 |
| M0-4 | Port interfaces (abstract) | ✅ Implemented | Define all Input/Output Port interfaces (`ClosetRepositoryPort`, `EmbeddingSearchPort`, `ClothingSearchPort`, `ImageStoragePort`, `TaskQueuePort`, `ImageGenerationPort`, etc.) — no implementations. | §5.1, §5.2 |
| M0-5 | Two-container project structure | ✅ Implemented | `fastapi-service` and `adk-agent-service` as separate buildable containers/apps. | §9.1, ADL-007 |
| M0-6 | `docker-compose.yml` (local deps) | ✅ Implemented | Elasticsearch 8.x (`localhost:9200`) + Firestore Emulator (`localhost:8080`) containerized. | §9.4, ADL-017 |
| M0-7 | `Makefile` dev commands | ✅ Implemented | `make dev` (start all), `make test`, `make clean`. | §9.4, ADL-017 |
| M0-8 | `.env.example` template | ✅ Implemented | Git-tracked env var template per §9.4 / §12.2. | §9.4, §12.2 |
| M0-9 | `README_LOCAL_DEV.md` | ✅ Implemented | Detailed local setup instructions. | §9.4, ADL-017 |
| M0-10 | Environment variable loading | ✅ Implemented | App reads all config (secret + non-secret) uniformly as env vars. | §12.1, §12.2 |

**Exit criteria:** `make dev` boots Elasticsearch + Firestore Emulator + FastAPI + ADK locally; project compiles with empty adapters.

---

## M1 — PoC & Infrastructure Validation

**Scope:** Resolve the three "Early PoC required" / Open Question items before downstream milestones depend on them. Reference: `req-phase01.md` §6.5 (PoC), §9.2, ADL-005, ADL-011, ADL-013, §17.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M1-1 | Image generation PoC script | ✅ Implemented | `poc/image_generation/run_poc.py` — feeds garment photos to Nano Banana (Gemini image model) for virtual try-on; collage fallback. Self-contained (`pip install -r requirements.txt`). | §6.5, ADL-005 |
| M1-2 | Image gen model decision | ✅ Implemented | **Decision: Nano Banana (`gemini-2.5-flash-image`); Imagen dropped** (subject-customization can't do multi-garment try-on). `gemini-3-pro-image-preview` is the quality-upgrade option. See ExecPlan Decision Log. | §6.5, ADL-005, §17 |
| M1-3 | Elasticsearch on Compute Engine PoC | 🟡 In progress | **Re-scoped 2026-06-04 (ExecPlan Decision Log).** M1 scope is local-only: confirm the JP-analyzer requirement against the Docker ES (`localhost:9200`) and record the deferral decision. GCE VM + VPC connector + Cloud Run connectivity + vector hybrid + shared-closet seeding are **deferred to the deployment phase** (~1–2 wk before submission). M2 proceeds against local ES behind `EmbeddingSearchPort` (keyword/Firestore adapter first). ADL-013 unchanged; only sequencing. | §9.2, ADL-013, §17 |
| M1-4 | ADK Event Stream granularity PoC | ✅ Implemented | `runner.run_async()` yields 3 `Event` objects per tool-call turn (ToolCall/ToolResult/FinalAnswer); batched (no streaming); `model_dump()` requires normalization before Firestore storage (`thought_signature`: bytes→base64; `long_running_tool_ids`: set→array). See ExecPlan Artifacts. | ADL-011, §17 |

**Exit criteria:** Image gen approach chosen; JP-analyzer requirement resolved against the local Docker ES and the ES deployment deferral decision recorded (GCE/VPC private-connectivity check moved to the deployment phase); ADK event format documented.

---

## M2 — Auth & Closet Management (Web)

**Scope:** Authenticated users upload, view, and delete closet images; uploaded images are analyzed and embedded asynchronously. Reference: `req-phase01.md` §6.7–6.10, §8, §10, §11, ADL-014, ADL-015.

> **ExecPlan (2026-06-04):** [20260604-m2-closet-management-backend.md](plans/20260604-m2-closet-management-backend.md) covers the **backend slice** of M2 — the nine server-side requirements M2-2…M2-10, all of which already have stubs in `fastapi-service` and are verifiable end-to-end against `make dev`. The three client-facing requirements (M2-1, M2-11, M2-12) are **deferred to a follow-up frontend plan** because no Flutter app exists in the repo yet; they stay ❌ until then.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M2-1 | Firebase Auth — Google Sign-In | ❌ Not yet implemented | Flutter Web login via Google Sign-In; first login creates `users/{uid}`. **Deferred:** needs a Flutter app (none exists yet); to be planned in a dedicated frontend ExecPlan **after** the [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) is complete. | §10.1, §15 Phase 1a #4 |
| M2-2 | FastAPI Firebase ID Token middleware | 🟡 In progress | `verify_firebase_token` dependency; rejects invalid tokens with 401. Planned in [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 1). | §10.3 |
| M2-3 | `GetUploadUrlUseCase` | 🟡 In progress | `GET /closet/upload-url` — issues 15-min R2 signed PUT URL; enforces `MAX_CLOSET_IMAGES_PER_USER`. Planned in [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 3). | §6.7 |
| M2-4 | `RegisterClothingItemUseCase` | 🟡 In progress | `POST /closet/items/{item_id}/complete` — writes Firestore placeholder, enqueues embed job. Planned in [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 3). | §6.8 |
| M2-5 | `ProcessUploadedClothingItemUseCase` | 🟡 In progress | `POST /internal/tasks/process-upload` — Gemini analysis + embedding, updates Firestore/ES. **Placement (2026-06-04):** implemented in `fastapi-service` (not `adk-agent-service`, which is a TS skeleton); embedding is best-effort. See [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) Decision Log. | §6.9, §8.3 |
| M2-6 | `DeleteClosetItemUseCase` | 🟡 In progress | `DELETE /closet/items/{item_id}` — deletes across Firestore + ES + R2. Planned in [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 3). | §6.10, ADL-015 |
| M2-7 | `R2ImageStorageAdapter` | 🟡 In progress | Cloudflare R2 signed URL issue + image fetch/delete; bucket CORS configured. **2026-06-04:** one boto3 S3 adapter, MinIO stand-in locally. See [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 2). | §5.2, §8.4, ADL-014 |
| M2-8 | `FirestoreClosetRepository` | 🟡 In progress | `users/{userId}/closet` metadata CRUD. Planned in [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 2). | §5.2, §8.1 |
| M2-9 | `ElasticsearchEmbeddingRepository` | 🟡 In progress | `clothing_items` index create/upsert/delete; hybrid search support. **Sequencing (2026-06-04):** build against the local Docker ES behind `EmbeddingSearchPort`, keyword/Firestore-backed first; vector hybrid + GCE host swapped in at the deployment phase. See [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 2). | §5.2, §8.2 |
| M2-10 | Cloud Tasks adapter (`TaskQueuePort`) | 🟡 In progress | `CloudTasksAdapter` — enqueue jobs to `CLOUD_TASKS_QUEUE_EMBED`. **2026-06-04:** plus a `LocalHttpTaskQueueAdapter` for local dev. See [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) (Phase 2). | §5.2, §6.8 |
| M2-11 | Flutter closet management UI | ❌ Not yet implemented | Upload (direct R2 PUT), list via Firestore realtime listener, delete. **Deferred:** needs a Flutter app (none exists yet); to be planned in a dedicated frontend ExecPlan **after** the [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) is complete. | §11, ADL-015 |
| M2-12 | Firebase Security Rules (closet) | ❌ Not yet implemented | Rules allowing per-user direct read of `users/{uid}/closet`. **Deferred:** pairs with the Flutter direct-read path; to be planned in a dedicated frontend ExecPlan **after** the [M2 backend ExecPlan](plans/20260604-m2-closet-management-backend.md) is complete. | ADL-015 |

**Exit criteria:** A logged-in user uploads an image → R2 stores it → Firestore metadata reaches `status: READY` → ES indexed; delete removes all three. *(The backend ExecPlan proves this at the API layer via `make dev` + a scripted curl flow; the Flutter client that drives it is the deferred follow-up plan.)*

---

## M3 — Shared Demo Closet

**Scope:** Provide a pre-seeded, read-only shared closet so first-time users can try coordination without uploading. Reference: `req-phase01.md` §16, ADL-010.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M3-1 | `run_seed.py` seeding script | ❌ Not yet implemented | `scripts/seed_shared_closet/run_seed.py` — Kaggle download → sample → R2 upload → embed → ES index → Firestore write. Idempotent. | §16.4, §15 Phase 1a #7 |
| M3-2 | `shared_closet` data populated | ❌ Not yet implemented | 2,000+ items seeded across Firestore + ES (`user_id: "__shared__"`) + R2. | §16, ADL-010, §15 Phase 1a #7 |
| M3-3 | `SharedClosetSearchAdapter` | ❌ Not yet implemented | `ClothingSearchPort` impl filtering ES by `user_id: "__shared__"`. | §5.2, §6.3, ADL-010 |
| M3-4 | Attribution display (CC BY-SA 4.0) | ❌ Not yet implemented | Web GUI footer/modal attribution; `CandidateItem.attribution` set for shared items. | §16.3 |

**Exit criteria:** Seeding script runs idempotently; `SHARED_CLOSET` source returns candidate items with attribution.

---

## M4 — ADK Agents Core

**Scope:** Implement the agent topology and tools; runnable locally on ADK Web UI. Reference: `req-phase01.md` §6.1–6.5, §7.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M4-1 | `StylingOrchestratorAgent` | ❌ Not yet implemented | Root agent delegating to sub-agents (ADK sub-agent delegation). | §7.1 |
| M4-2 | `ClosetAgent` | ❌ Not yet implemented | Closet search & management sub-agent. | §7.1 |
| M4-3 | `StylingAgent` | ❌ Not yet implemented | Coordination generation & proposal sub-agent. | §7.1 |
| M4-4 | Tool Registry pattern | ❌ Not yet implemented | Each tool an independent module registered via a registry. | §7.2 |
| M4-5 | `analyze_clothing_image` tool | ❌ Not yet implemented | Gemini 2.0 Flash structured-output image analysis. Backs `AnalyzeClothingImageUseCase`. | §6.1, §7.2 |
| M4-6 | `search_closet` tool | ❌ Not yet implemented | Cross-modal hybrid search over ES (closet + shared closet). | §6.3, §7.2, §8.3 |
| M4-7 | `style_synthesizer` tool | ❌ Not yet implemented | Final coordinate image generation via model chosen in M1-2; collage fallback. | §6.5, §7.2 |
| M4-8 | `ask_preference` tool | ❌ Not yet implemented | Collects `UserPreference`. (LINE interactive variant deferred to M6; Web uses text input.) | §6.4, §7.2 |
| M4-9 | `AGENT_MODEL` override | ❌ Not yet implemented | All agents default to `gemini-2.0-flash`, overridable via `AGENT_MODEL` env var. | §7.1, §12.2 |

**Exit criteria:** Orchestrator + sub-agents run on local ADK Web UI; each tool callable end-to-end (§15 Phase 1a #1).

---

## M5 — Coordination Flow & Accordion UI (Web E2E)

**Scope:** Wire the full Web GUI coordination flow with live agent-thinking visualization. Reference: `req-phase01.md` §6.1–6.5, §6.11, §8.1, §11, ADL-009, ADL-011.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M5-1 | `CreateSessionUseCase` | ❌ Not yet implemented | `POST /sessions` — creates `sessions/{id}` with `status: SOURCE_SELECTING`. | §6.11, ADL-015 |
| M5-2 | `FirestoreStyleSessionRepository` | ❌ Not yet implemented | Session state persistence + state machine transitions. | §5.2, §8.1 |
| M5-3 | `SelectClothingSourceUseCase` | ❌ Not yet implemented | Updates session `source`; validates `CLOSET` has data, `SHARED_CLOSET` always allowed. | §6.2, §4.3 |
| M5-4 | `AnalyzeClothingImageUseCase` | ❌ Not yet implemented | Analyzes image, saves result, transitions session to analyzed. | §6.1 |
| M5-5 | `SearchCandidateItemsUseCase` | ❌ Not yet implemented | Routes to closet/shared/Rakuten adapters; returns unified `CandidateItem` list. | §6.3, ADL-008 |
| M5-6 | `GenerateCoordinateUseCase` | ❌ Not yet implemented | Generates final coordinate image; session → `COMPLETED`. | §6.5, §4.3 |
| M5-7 | Session lifecycle & timeout | ❌ Not yet implemented | One image per session; new upload after `COMPLETED`/timeout → new session. | §4.3, ADL-009 |
| M5-8 | ADK → Firestore event relay | ❌ Not yet implemented | ADK writes `sessions/{id}/agentEvents/{eventId}`; event subcollection TTL. | ADL-011 |
| M5-9 | SSE streaming endpoint | ❌ Not yet implemented | `GET /sessions/{id}/stream` — FastAPI Firestore `on_snapshot` → SSE to Flutter. | §15 Phase 1a #2, ADL-011 |
| M5-10 | Flutter Accordion UI | ❌ Not yet implemented | Receives SSE, renders agent thinking steps as collapsible real-time UI. | §11, §15 Phase 1a #3 |
| M5-11 | Web coordination flow E2E | ❌ Not yet implemented | upload → agent thinking → candidates → select → image generated, fully working. | §15 Phase 1a #6 |

**Exit criteria:** Full Phase 1a flow works end-to-end in the browser with live Accordion UI; `shared_closet` source produces a generated coordinate image.

---

## M6 — LINE Channel Integration (Phase 1b)

**Scope:** Bring the coordination experience to LINE; add Rakuten search. **Do not start before M5 is complete** (`req-phase01.md` §14). Reference: `req-phase01.md` §6.4, §6.6, §7.3, §7.4, §10.2, ADL-006, ADL-009.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M6-1 | LINE Webhook endpoint | ❌ Not yet implemented | Signature verification; immediate `200 OK`. | §7.4, §15 Phase 1b #1, ADL-006 |
| M6-2 | Cloud Tasks async agent execution | ❌ Not yet implemented | Webhook → `CLOUD_TASKS_QUEUE_AGENT` → async ADK agent run. | §7.4, §15 Phase 1b #2 |
| M6-3 | `LineReplyAdapter` (Reply + Push) | ❌ Not yet implemented | Reply API with Push API fallback when `replyToken` expires. | §6.6, §7.4, ADL-006, ADL-009 |
| M6-4 | `ReplyCoordinateToLineUseCase` | ❌ Not yet implemented | Sends final coordinate image + text to LINE. | §6.6 |
| M6-5 | `search_rakuten` tool + adapter | ❌ Not yet implemented | `RakutenItemAdapter`; calls routed via Cloud Tasks. | §6.3, §7.2 |
| M6-6 | Rakuten rate-limit enforcement | ❌ Not yet implemented | `CLOUD_TASKS_QUEUE_RAKUTEN` with `maxConcurrentDispatches: 1` (1 req/sec). | §7.3, §15 Phase 1b #4, ADL-002 |
| M6-7 | `AskUserPreferenceUseCase` (LINE) | ❌ Not yet implemented | LINE interactive message variant of preference collection. | §6.4 |
| M6-8 | LIFF account linking flow | ❌ Not yet implemented | `POST /auth/line-link` — verify LINE token, mint Firebase Custom Token, write `users`/`lineUsers`. | §10.2 |
| M6-9 | `lineUserId` → `userId` resolution | ❌ Not yet implemented | `resolve_user` lookup; unregistered users routed to LIFF signup. | §10.3, §8.1 |
| M6-10 | LINE session flow E2E | ❌ Not yet implemented | LINE image upload → analysis → source/candidate selection → coordinate image reply. | §1 Phase 1b, §15 Phase 1b #3 |

**Exit criteria:** A LINE user completes the full coordination flow and receives a coordinate image in the LINE chat.

---

## Out of scope (Phase 1)

Per `req-phase01.md` §14 — not tracked in this matrix:

- Background removal
- User scoring/rating beyond explicit feedback
- Admin dashboard (Phase 2)
- Ranking-score recommendation optimization (Phase 2)
- OMO features
- BtoB features
- Google Sign-In ↔ LINE account unification (Phase 2)
