# Phase 1 Feature Matrix — gen-fashion

> **Last updated:** 2026-06-09 — M3 + M4 ExecPlans created. M3 ([20260609-m3-shared-demo-closet.md](plans/20260609-m3-shared-demo-closet.md)): M3-1/M3-3/M3-4 → 🟡, M3-2 → 🟡 (partial; local subset now, full vector seed at deployment per M1-3). M4 ([20260609-m4-adk-agents-core.md](plans/20260609-m4-adk-agents-core.md)): M4-1…M4-9 → 🟡, `adk-agent-service` rebuilt in Python ADK (ADL-022). M3 & M4 are unblocked siblings feeding M5; recommended order **M3 → M4**. Prior: 2026-06-07 — M2 frontend ExecPlan complete (M2-1/M2-11/M2-12 → ✅: rules 7/7, Flutter analyze/test 6/6, backend pytest 34 passed, full sign-in → upload → PROCESSING → READY → delete browser E2E against `make dev`).
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

> **ExecPlan (2026-06-04):** [20260604-m2-closet-management-backend.md](plans/20260604-m2-closet-management-backend.md) covers the **backend slice** of M2 — the nine server-side requirements M2-2…M2-10, which are verifiable end-to-end against `make dev`. This backend plan is **complete** (M2-2…M2-10 are ✅).
>
> **ExecPlan (2026-06-06, complete 2026-06-07):** [20260606-m2-closet-management-frontend.md](plans/20260606-m2-closet-management-frontend.md) covers the **frontend slice** of M2 — the three client-facing requirements M2-1, M2-11, M2-12 — built in a new `flutter-web-app/` (Google Sign-In, closet upload/list/delete UI, Firestore Security Rules) that drives the backend above. It also added **one additive, read-only backend endpoint** (`GET /closet/items/{id}/download-url`) so closet thumbnails load via short-lived signed URLs while storage stays private (R2-ready). Acceptance observed 2026-06-07: backend pytest 34 passed; rules unit test 7/7; `flutter analyze` clean and `flutter test` 6/6; browser E2E (sign-in → upload → PROCESSING → READY → delete) against `make dev`. **All three rows → ✅. Milestone M2 fully Implemented.**
>
> **Backend implementation status (2026-06-04):** M2-2…M2-10 are implemented. `pytest -q` passes (`28 passed`) with live Elasticsearch reachable from Compose. Docker Compose boots Firestore Emulator, Firebase Auth Emulator, MinIO, Elasticsearch, and FastAPI. `scripts/m2_closet_smoke.py --expect-status ERROR` passes with the default dummy Gemini key, and `scripts/m2_closet_smoke.py --expect-status READY` passes with the `.env` Gemini key, proving authenticated signed upload, storage, Firestore READY metadata, local worker dispatch, Elasticsearch indexing, and delete cleanup.
>
> ⚠️ **BLOCKING deploy security gate (M2-5 internal route):** the `POST /internal/tasks/process-upload` worker route is now guarded by a fail-closed shared secret (`INTERNAL_TASK_SECRET`, header `X-Internal-Secret`) for local/defense-in-depth. **Before any public deploy, the M2 ExecPlan Decision Log gate must hold:** `CloudTasksAdapter` sets an OIDC token verified by the worker, Cloud Run `fastapi-service` ingress is set to `internal`, and `INTERNAL_TASK_SECRET` is a real Secret-Manager value. Tracked via `# TODO(deploy)` in `app/adapters/cloud_tasks_adapter.py`.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M2-1 | Firebase Auth — Google Sign-In | ✅ Implemented | Flutter Web login via Google Sign-In; first login creates `users/{uid}`. Implementation lives in `flutter-web-app/lib/auth/`: `auth_gate.dart` (StreamBuilder on `authStateChanges`), `auth_service.dart` (`signInWithPopup(GoogleAuthProvider())` + first-login `users/{uid}` bootstrap), `login_screen.dart`. Verified 2026-06-07 in headless Chromium against `make dev`: login screen renders with "Sign in with Google" button, popup opens at `localhost:9099` ("Sign-in with Google.com" via the Auth Emulator's mock provider), filling "E2E Tester" / `e2e@example.com` and submitting flips the `AuthGate` to `ClosetScreen` (count chip "1 / 20"), proving the `users/{uid}` bootstrap path. | §10.1, §15 Phase 1a #4 |
| M2-2 | FastAPI Firebase ID Token middleware | ✅ Implemented | `verify_firebase_token` dependency implemented; Firebase Auth Emulator token smoke passes; route tests verify missing bearer token returns 401. | §10.3 |
| M2-3 | `GetUploadUrlUseCase` | ✅ Implemented | `GET /closet/upload-url` returns a 15-min signed PUT URL and enforces `MAX_CLOSET_IMAGES_PER_USER`; live READY smoke uploads through a host-reachable MinIO signed URL. | §6.7 |
| M2-4 | `RegisterClothingItemUseCase` | ✅ Implemented | `POST /closet/items/{item_id}/complete` writes a PROCESSING placeholder and enqueues the worker task; live smoke proves Firestore placeholder + local worker dispatch. | §6.8 |
| M2-5 | `ProcessUploadedClothingItemUseCase` | ✅ Implemented | `POST /internal/tasks/process-upload` in `fastapi-service` fetches storage bytes, runs Gemini analysis, handles embedding best-effort, updates Firestore READY/ERROR, and indexes ES. Live READY and ERROR smoke paths pass. **Security (2026-06-04):** the internal route is guarded by a fail-closed shared secret; production OIDC + Cloud Run internal ingress is a BLOCKING deploy gate (see note above). | §6.9, §8.3 |
| M2-6 | `DeleteClosetItemUseCase` | ✅ Implemented | `DELETE /closet/items/{item_id}` performs best-effort ES/storage deletion and authoritative Firestore deletion; READY smoke confirms removal from Firestore, Elasticsearch, and storage. | §6.10, ADL-015 |
| M2-7 | `R2ImageStorageAdapter` | ✅ Implemented | One boto3 S3-compatible adapter handles R2/MinIO signed URLs, byte fetch, existence check, and delete; live smoke proves MinIO object upload/presence/delete. | §5.2, §8.4, ADL-014 |
| M2-8 | `FirestoreClosetRepository` | ✅ Implemented | Async Firestore CRUD/count for `users/{userId}/closet` with domain/document mapping, including `embeddingId: item_id` for READY documents; READY smoke verifies metadata fields. | §5.2, §8.1 |
| M2-9 | `ElasticsearchEmbeddingRepository` | ✅ Implemented | `clothing_items` index create/upsert/delete and keyword-first search implemented; live ES adapter test passes and READY smoke verifies worker-created ES document. | §5.2, §8.2 |
| M2-10 | Cloud Tasks adapter (`TaskQueuePort`) | ✅ Implemented | `CloudTasksAdapter` plus async fire-and-forget `LocalHttpTaskQueueAdapter`, selected by settings; tests and smoke prove enqueue isolation and internal-worker dispatch. | §5.2, §6.8 |
| M2-11 | Flutter closet management UI | ✅ Implemented | Upload (direct MinIO/R2 PUT), list via Firestore realtime listener, delete. Implementation in `flutter-web-app/lib/closet/`: `closet_screen.dart` (grid + `users/{uid}/closet` snapshots stream + `N / 20` count), `closet_item.dart`, `thumbnail.dart` (FutureBuilder on the new signed-GET endpoint with a per-session cache), `upload_service.dart` (pick → signed PUT → complete; 429 → SnackBar), delete confirmation dialog. Backend additive endpoint `GET /closet/items/{id}/download-url` (Phase 3); `pytest -q` reports **34 passed, 1 skipped**. `flutter analyze` reports **No issues found**; `flutter test` reports **6/6 pass** (widget grid + API client). Verified 2026-06-07 in headless Chromium against `make dev`: upload via signed PUT places a PROCESSING card (amber spinner + "Analyzing…") which transitions live to READY (green badge) without polling; count goes 1 → 2; signed-URL thumbnail renders; delete drops the count to 1 / 20. | §11, ADL-015 |
| M2-12 | Firebase Security Rules (closet) | ✅ Implemented | Rules allowing per-user direct read of `users/{uid}/closet`. `firestore.rules` at repo root (owner read on `users/{uid}` and `users/{uid}/closet/*`, all client writes denied, default-deny everywhere else); `firebase.json` extended with the `firestore` block + emulator port; `@firebase/rules-unit-testing` suite at `firebase/firestore-rules.test.mjs` covers owner allow + cross-user deny + client-write deny + first-login `users/{uid}` create + unauth deny. Verified 2026-06-06: `firebase emulators:exec --only firestore --project gen-fashion-local "npm test"` reports **7 pass / 0 fail** against the rule-enforcing emulator. | ADL-015 |

**Exit criteria:** A logged-in user uploads an image → R2 stores it → Firestore metadata reaches `status: READY` → ES indexed; delete removes all three. *(The backend ExecPlan proves this at the API layer via `make dev` + a scripted curl flow; the Flutter client that drives it is the deferred follow-up plan.)*

---

## M3 — Shared Demo Closet

**Scope:** Provide a pre-seeded, read-only shared closet so first-time users can try coordination without uploading. Reference: `req-phase01.md` §16, ADL-010.

> **ExecPlan (2026-06-09):** [20260609-m3-shared-demo-closet.md](plans/20260609-m3-shared-demo-closet.md) covers all four M3 requirements. Built against **local infra now** (keyword-first, seeded subset); per the **M1-3** re-scope the full 2,000+ vector seed on the GCE-hosted Elasticsearch is a **deployment-phase re-run** of the same script (`--with-embeddings`, `MAX_ITEMS_PER_CATEGORY=150`). M3-1/M3-3/M3-4 → 🟡; **M3-2 → 🟡 (partial)** — local subset seeded now, full-scale seed deferred. M3 and M4 are **unblocked siblings** feeding M5 (no dependency between them); recommended working order **M3 → M4** since M3 is smaller/lower-risk and enriches the M4 demo with the `SHARED_CLOSET` source. No `req-phase01.md` change (fully specified by §16 / §8 / ADL-010).

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M3-1 | `run_seed.py` seeding script | 🟡 In progress | `scripts/seed_shared_closet/run_seed.py` — Kaggle download → sample → R2 upload → embed → ES index → Firestore write. Idempotent (`item_id = uuid5(filename)`); self-contained per §16.4. | §16.4, §15 Phase 1a #7 |
| M3-2 | `shared_closet` data populated | 🟡 In progress (partial) | 2,000+ items across Firestore + ES (`user_id: "__shared__"`) + R2. **Local keyword-first subset now; full vector seed on GCE ES deferred to deployment (M1-3).** | §16, ADL-010, §15 Phase 1a #7 |
| M3-3 | `SharedClosetSearchAdapter` | 🟡 In progress | `ClothingSearchPort` impl filtering ES by `user_id: "__shared__"`; keyword-first + fail-soft kNN; sets `attribution`. Own ES client (M2-9 repo untouched). | §5.2, §6.3, ADL-010 |
| M3-4 | Attribution display (CC BY-SA 4.0) | 🟡 In progress | `CandidateItem.attribution = "Clothing Dataset (CC BY-SA 4.0)"`; Flutter footer/"About the shared closet" modal. Per-candidate-card display wired in M5. | §16.3 |

**Exit criteria:** Seeding script runs idempotently; `SHARED_CLOSET` source returns candidate items with attribution.

---

## M4 — ADK Agents Core

**Scope:** Implement the agent topology and tools; runnable locally on ADK Web UI. Reference: `req-phase01.md` §6.1–6.5, §7.

> **ExecPlan (2026-06-09):** [20260609-m4-adk-agents-core.md](plans/20260609-m4-adk-agents-core.md) covers the **whole M4 milestone** — the nine requirements M4-1…M4-9 — and is the critical path to M5. All nine rows → 🟡 **In progress** (plan in flight). The plan's load-bearing decision: **`adk-agent-service` is rebuilt in Python ADK**, replacing the current TypeScript skeleton (recorded as **ADL-022** in `req-phase01.md`; forced by req §2, the Python M1-4 PoC `runner.run_async()`, ADL-021's shared `FirestoreStyleSessionRepository`, and reuse of the existing Python Gemini/ES/image-gen adapters). M4 stops at "runs on the ADK Web UI and each tool is callable end-to-end"; the FastAPI session routes, the Firestore `agentEvents` relay (ADL-011/ADL-021), SSE, and the Flutter Accordion/A2UI result UI are **M5**. A2UI agent-side output (ADL-018) is deferred to M5's result UI.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M4-1 | `StylingOrchestratorAgent` | 🟡 In progress | Root agent delegating to sub-agents (ADK sub-agent delegation). Built in Python ADK as the `styling_app` `root_agent` (ADL-022). | §7.1 |
| M4-2 | `ClosetAgent` | 🟡 In progress | Closet search & management sub-agent. Tools `[analyze_clothing_image, search_closet]`. | §7.1 |
| M4-3 | `StylingAgent` | 🟡 In progress | Coordination generation & proposal sub-agent. Tools `[ask_preference, style_synthesizer]`. | §7.1 |
| M4-4 | Tool Registry pattern | 🟡 In progress | Each tool an independent module registered via a registry (`tools/registry.py`). | §7.2 |
| M4-5 | `analyze_clothing_image` tool | 🟡 In progress | Gemini structured-output image analysis; reuses the M2-5 response schema. Backs `AnalyzeClothingImageUseCase`. | §6.1, §7.2 |
| M4-6 | `search_closet` tool | 🟡 In progress | Cross-modal hybrid search over ES (closet + shared closet). Keyword-first + additive fail-soft kNN (M1-3). | §6.3, §7.2, §8.3 |
| M4-7 | `style_synthesizer` tool | 🟡 In progress | Final coordinate image generation via Nano Banana (`gemini-2.5-flash-image`, M1-2); collage fallback (ADL-005). | §6.5, §7.2 |
| M4-8 | `ask_preference` tool | 🟡 In progress | Normalizes/echoes the pre-session-form `UserPreference` (Web, §6.4). LINE interactive variant deferred to M6. | §6.4, §7.2 |
| M4-9 | `AGENT_MODEL` override | 🟡 In progress | All agents default to `gemini-2.0-flash`, overridable via `AGENT_MODEL` env var. | §7.1, §12.2 |

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
