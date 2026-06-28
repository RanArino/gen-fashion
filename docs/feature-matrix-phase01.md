# Phase 1 Feature Matrix — gen-fashion

> **CI/CD planning (2026-06-26 — tracking only, no ExecPlan yet):** The hackathon's
> judging axis — **CI/CD after deployment** — was not present anywhere in the
> requirements or plans (no `.github/`, no Cloud Build trigger, no `cloudbuild.yaml`,
> no `scripts/deploy/`; "CI/CD" never appears in req/matrix; the MD plan is
> deliberately manual `gcloud` + shell scripts, ADL rejecting Terraform). Added a new
> milestone **MF (CI/CD)** with rows **MF-1…MF-6** to track it. Platform: **GitHub
> Actions + Workload Identity Federation** (ADL-030 / ADL-031 / ADL-032, req §19). MF
> automates MD's manual deploy steps and **depends on MD**. Per **"one ExecPlan at a
> time"** the CI/CD ExecPlan is **not authored yet** (MD is the resume-next milestone);
> this change is **req/matrix tracking only, no code** — the same method used for the
> ME pre-deploy audit. **MF rows are ❌ Not yet implemented.**

> **ME-7 completion update (2026-06-24): ✅ Implemented.** Completed ADK runs
> now receive an authoritative Firestore `completedAt`; authenticated
> `GET /sessions` returns the owner's completed runs newest first; and Flutter
> has a History gallery for generated images, dates, source labels, and selected
> garments. The required composite index is declared. Verification: FastAPI 68
> passed, ADK 41 passed, Flutter analyze clean / 14 passed; live session
> `a86d94c8-…` completed and was returned by history with a server timestamp and
> generated image. Weather, recent-wear deduplication, retries, and cursor
> pagination remain future scope.

> **Completion update (2026-06-21): ME-1…ME-6 are ✅ Implemented.** The two
> must-fix gates are closed: child runs carry child/gender context and image
> generation is structurally blocked until explicit candidate selection. Local
> evidence after the agent-flow recovery: FastAPI 64 passed, ADK 36 passed,
> Flutter analyze clean/12 passed; real two-run ADK smokes completed adult session
> `02ea5e0b-…` and child session `0adfd256-…` without search fallback; rendered
> browser E2E session `268d9a09-…` completed with transfer/search/synthesis events
> and no fallback.
> The child result is a visually confirmed child image. ME-7 remains deferred;
> MD may resume.

> **Prior update (plan authoring):** 2026-06-21 — **ME ExecPlan authored; MD paused for ME.** New ExecPlan [20260621-me-pre-deployment-experience-domain-hardening.md](plans/20260621-me-pre-deployment-experience-domain-hardening.md) selects **ME-1…ME-6** (ME-7 run-history deferred to a post-MD plan): a gender/age dimension threaded end-to-end (heuristic gender data + `UserPreference.gender` → search/styling/**child-01 child imagery**, ME-2/3/4), a **mandatory candidate-selection gate** implemented as a two-phase ADK run (propose → pause at `PROPOSING` → `POST /sessions/{id}/select` → generate; ME-6), trace curation + result-UI split (ME-5), and a browsable closet gallery with editable own-item metadata (ME-1). **ME-2…ME-6 → 🟡 In progress** (ME-1 already 🟡; ME-7 stays ❌). `docs/architecture-overview.md` synced with the ME-planned additions. **MD is paused** (per the `ToDo` framing) until ME's must-fix subset (ME-3, ME-6) is closed. **Prior (2026-06-21): Pre-deployment gap audit (`ToDo` §1–6) before starting MD: investigated six user-facing / domain gaps and added a new milestone [ME](#me--pre-deployment-experience--domain-hardening) (ME-1…ME-7) to track them; MD is now gated on ME's must-fix subset.** Findings (no code changed this turn — matrix-only tracking per the "one ExecPlan at a time" rule, MD still the active ExecPlan): (1) **closet gallery** exists for the user's own closet (minimal metadata — category + ≤3 tags, `closet_screen.dart`) but there is **no browse view for the shared closets** — `adult-01/adult-02/child-01` are only a dropdown of IDs in `coordination_screen.dart`; `shared_closets/*` metadata + per-item `shared_closet/*` docs exist with **no list endpoint** (`closet_routes.py` is own-closet only). (2/3) **No gender/age dimension anywhere** — `UserPreference` is occasion/season/style/color only, and the Flutter form, `search_closet`, `style_synthesizer`, and `ask_preference` carry no gender; the seed (`run_seed.py`) writes `closetKind` (adult/child) but **no gender**, and the Kaggle dataset has no gender column (req §16 note). `closetKind="child"` is **never propagated** to search/styling/image-gen, so selecting `child-01` still generates **adult** imagery — a real defect (ME-3, must-fix). (4) **Agent Trace too granular** — `events.py` emits a tile per `tool_call`/`tool_result`/`final_answer`/`transfer_to_agent`, and `AgentEventTile` renders every one as a raw `ExpansionTile` dump, mixing the thinking trace with would-be result data (ADL-018 says these are separate streams). (5) **No candidate selection** — `search_closet` results are in the event stream but only dumped as raw text; `StylingAgent` auto-calls `style_synthesizer` with **no user-approval gate**, which **violates req §3 ("同意なき自動生成禁止") and req §15 Phase 1a #6 ("候補提示 → 選択 → 画像生成")**; the `PROPOSING` state exists but never pauses. So **M5-6/M5-11's "§15 #6 satisfied" claim is overstated** (selection step missing; ADL-018 result UI deferred at M5 and never built) — tracked as ME-6 (must-fix). (6) **No run history** — `session_routes.py` has only create/source/stream, `FirestoreStyleSessionRepository` has no list-sessions, and there is no history gallery, weather signal, or duplication-avoidance (user-flagged future expansion, ME-7). **Prior (2026-06-21): Local re-verification before deploy (checklist [20260621-md-phase1a-local-verification-checklist.md](plans/20260621-md-phase1a-local-verification-checklist.md)) found three real bugs that the prior "verified locally" claims had masked; all fixed and re-verified.** (1) **Internal worker base-URL conflation actually broke `make dev`:** the `process-upload` task POSTed to `ADK_INTERNAL_BASE_URL` (adk:3000) which 404s — closet upload→READY never completed locally. Landed the **local portion of MD-8** early: new `fastapi_internal_base_url` setting + `FASTAPI_INTERNAL_BASE_URL=http://fastapi-service:8000` in `docker-compose.yml` (OIDC/cloud-tasks parts still open under MD-8). (2) **Firestore project split:** backend used the Vertex project (`GOOGLE_CLOUD_PROJECT=animation-agent`) for the Firestore client too, writing to a different emulator namespace than the frontend/auth (`gen-fashion-local`) — UI could not see closet/session data. Added `firestore_project_id` (= Firebase project) to both services + `FIREBASE_PROJECT_ID` to the adk compose env; no-op in prod (all projects equal). (3) **`closetId` was dynamic `text`** because `fastapi-service`'s `ensure_index` mapping omitted it (created the index before the seed) → SHARED_CLOSET term filter matched 0 docs → coordination ended `ERROR`. Added `closetId`/`closetKind`/`imageUrl` as keyword to the canonical M2-9 mapping (`elasticsearch_embedding_repo.py`), reindexed + reseeded. After fixes: fastapi pytest **59 passed**, adk pytest **28 passed**, flutter analyze/test clean; M2 closet smoke → READY; M5 coordination smoke + **rendered browser E2E both reached `COMPLETED`** (session `1e91e195-…`, 24 events, final_answer) with a **real Nano Banana image** (`modelUsed=gemini-2.5-flash-image`, ~1.15 MB) — i.e. **the M4-7/M5-6 "collage fallback only locally" caveat no longer holds: Vertex image-gen works locally with the SA in project `animation-agent`.** **Same-day follow-up (both prior open items resolved):** (i) embedding fixed — `gemini-embedding-2` (nonexistent) → **`gemini-embedding-001`** (768-dim `embed_content`), and the index side now embeds the item's **analyzed text** (not the image) so it shares the text-query space; `--with-embeddings` seed produced 90 768-dim vectors and a kNN probe returns semantically relevant hits (de-risks MD-10; the seed's Vertex project was also split from its Firestore project, mirroring the app fix). (ii) ADK timeout made configurable (`adk_run_timeout_seconds`, 45→**90**) and the fastapi SSE bound raised (`STREAM_MAX_SECONDS` 120→**150**) so it always outlasts the ADK timeout + fallback — the T3-2 rerun completed via the **primary** LLM path (no fallback/TIMEOUT). fastapi pytest 59 / adk pytest 28 still green. Prior: 2026-06-15 — **MD (Phase 1a Production Deployment & Hardening) planned → MD-1…MD-14 🟡 In progress.** New ExecPlan [20260615-md-phase1a-production-deployment.md](plans/20260615-md-phase1a-production-deployment.md) selects the deployment cluster the docs repeatedly defer: Compute Engine Elasticsearch + Cloud Run private connectivity (completes **M1-3**), the full **vector** seed of the shared closet (`--with-embeddings`, **M3-2** deployment portion), the production security gate (OIDC + Secret Manager, **M2-5** deploy gate), and real Nano Banana image generation on Vertex AI (**M4-7/M5-6** caveat). Two deployment-blocking wiring facts surfaced while planning: `ADK_INTERNAL_BASE_URL` is conflated — the `process-upload` worker route lives in `fastapi-service` but the task adapters target the ADK URL (fixed in MD-8 via a new `FASTAPI_INTERNAL_BASE_URL`); and the M2 note's "`fastapi-service` ingress=internal" cannot hold (it serves the browser) — superseded by OIDC + shared-secret on the worker route (ADL-024). New ADLs ADL-023 (VPC Access connector), ADL-024 (internal-route OIDC), ADL-025 (Firebase Hosting) added to `req-phase01.md`. **Do not start M6 (LINE) — Phase 1b.** Prior: 2026-06-14 — **M5 complete: M5-1…M5-11 → ✅.** FastAPI session contracts/routes/repository, direct ADK trigger adapter, `adk-agent-service` `/internal/run-session` wrapper/event writer, FastAPI SSE polling stream, and Flutter Coordination tab/Accordion UI are implemented. Verified: `fastapi-service` pytest 59 passed; `adk-agent-service` pytest 25 passed; `flutter analyze` clean; `flutter test` 11 passed; local Docker/API smoke `python3 scripts/m5_coordination_smoke.py --timeout-seconds 180` completed authenticated `SHARED_CLOSET` session `1ce4c9f3-c2b3-4b20-9c4b-5494038d824d` through SSE with status `COMPLETED`; rendered Flutter Web browser E2E `python3 scripts/m5_coordination_browser_e2e.py --timeout-seconds 220` completed session `665b0a6f-531f-49e8-aa10-ae6e19b8a100` with `COMPLETED`, 26 events, `search_closet`, `style_synthesizer`, and result image evidence (screenshot `/tmp/m5-browser-e2e.png`). Prior: M5 ExecPlan [20260612-m5-coordination-flow-accordion-ui.md](plans/20260612-m5-coordination-flow-accordion-ui.md) selected the whole Web coordination milestone (M5-1…M5-11). Prior: 2026-06-11 — **M4 complete: M4-1…M4-9 → ✅.** `adk-agent-service` rebuilt in Python ADK (`google-adk` 2.1.0, ADL-022; TS skeleton deleted). Verified: `adk web` / `adk api_server` list `styling_app`; live `SHARED_CLOSET` coordination turn — orchestrator → ClosetAgent delegation → 3× `search_closet` calls returning M3-seeded `__shared__` items with CC BY-SA 4.0 attribution + signed MinIO URLs → StylingAgent → `style_synthesizer` storing a reachable coordinate image (collage fallback; Nano Banana path implemented but local free-tier key has no image-gen quota); `pytest -q` 17 passed (registry + 4 tools + agent topology + storage URL regression, mocked clients); docker image builds and `adk api_server` container runs healthy. ES keyword search fixed for keyword-typed fields (tokenized case-insensitive terms — see ExecPlan Surprises); ADK-owned signed MinIO/R2 URLs are resolved back to storage keys for container-side image fetches. Prior: 2026-06-10 — M3-2 multi-closet **live seed run & verified** against local infra (ES+MinIO+Firestore emulator): `created=90`, ES per-`closetId` 30/30/30 (adult-01/adult-02/child-01), MinIO 90 objects, Firestore `shared_closet/*` + 3 `shared_closets/*` metadata docs, no underwear/junk, idempotent re-run `created=0`; adapter pytest 8 passed + `flutter analyze` clean. **M3-2 → ✅ (local subset)**; full 2 000+ vector seed on GCE ES still deployment-deferred (M1-3). All M3 rows now ✅. Prior: 2026-06-09 — M3 code implementation complete. M3-1/M3-3/M3-4 → ✅; M3-2 → 🟡 (partial). `SharedClosetSearchAdapter` unit-tested, `flutter analyze` clean. M4 ([20260609-m4-adk-agents-core.md](plans/20260609-m4-adk-agents-core.md)): M4-1…M4-9 → 🟡, `adk-agent-service` rebuilt in Python ADK (ADL-022). Prior: 2026-06-09 — M3 + M4 ExecPlans created. M3 & M4 are unblocked siblings feeding M5; recommended order **M3 → M4**. Prior: 2026-06-07 — M2 frontend ExecPlan complete (M2-1/M2-11/M2-12 → ✅: rules 7/7, Flutter analyze/test 6/6, backend pytest 34 passed, full sign-in → upload → PROCESSING → READY → delete browser E2E against `make dev`).
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
| **ME** | Pre-Deployment Experience & Domain Hardening | 1a | M5 | Close six user-facing / domain gaps found before deploy (`ToDo` §1–6): closet gallery + metadata incl. shared closets, a gender/age dimension threaded end-to-end (child closet → child imagery), shared-closet gender data, Agent-Trace curation, candidate result UI + mandatory user-selection gate, and agent run history. |
| **MD** | Phase 1a Production Deployment & Hardening | 1a | M5, ME | Deploy the verified Phase 1a stack to Google Cloud: Compute Engine ES + private connectivity, full vector seed, Cloud Run ×2, Secret Manager + OIDC, Nano Banana on Vertex AI, Firebase Hosting. |
| **MF** | CI/CD (Continuous Delivery) | 1a | MD | Automate MD's manual deploy: GitHub Actions CI gate (per-service tests + image build) + CD (Artifact Registry → Cloud Run ×2 + Firebase Hosting) over Workload Identity Federation, with post-deploy smoke + revision rollback. The hackathon's CI/CD-after-deployment axis. |
| **M6** | LINE Channel Integration | 1b | M5 | LINE users get the full coordination experience; Rakuten search added. |

> Phase 1a = **M0–M5** (local-verified) **+ ME** (pre-deploy UX / domain hardening) **+ MD** (production cutover) **+ MF** (CI/CD automation over MD). Phase 1b = **M6**. **ME precedes MD** — MD's must-fix gate is the two requirement violations it found (the `child-01` → adult-image defect **ME-3** and the missing user-selection step **ME-6**); the rest of ME is strongly recommended before cutover. **MD** completes Phase 1a in the cloud and is independent of M6; LINE work (M6) must not start until M5 is complete (`req-phase01.md` §14).

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
| M0-7 | `Makefile` dev commands | ✅ Implemented | `make dev` starts services without reseeding; `make clean` snapshots Firestore to the named `gen-fashion_firestore-data` volume and stops containers; `make reset` is the explicit destructive reset. Firestore container recreation restored 3 closets / 210 items without a seed rerun (2026-06-24). | §9.4, ADL-017 |
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
| M1-3 | Elasticsearch on Compute Engine PoC | 🟡 In progress | **Re-scoped 2026-06-04 (ExecPlan Decision Log).** M1 scope is local-only: confirm the JP-analyzer requirement against the Docker ES (`localhost:9200`) and record the deferral decision. GCE VM + VPC connector + Cloud Run connectivity + vector hybrid + shared-closet seeding are **deferred to the deployment phase** (~1–2 wk before submission). M2 proceeds against local ES behind `EmbeddingSearchPort` (keyword/Firestore adapter first). ADL-013 unchanged; only sequencing. **2026-06-15:** the deferred GCE-ES + Cloud Run private-connectivity portion is now planned in the **MD** deployment ExecPlan ([20260615-md-phase1a-production-deployment.md](plans/20260615-md-phase1a-production-deployment.md), rows MD-3/MD-4) using **Direct VPC egress** (ADL-023, re-scoped 2026-06-27 from a Serverless VPC Access connector for hackathon cost). | §9.2, ADL-013, ADL-023, §17 |
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
| M2-9 | `ElasticsearchEmbeddingRepository` | ✅ Implemented | `clothing_items` index create/upsert/delete and keyword-first search implemented; live ES adapter test passes and READY smoke verifies worker-created ES document. **2026-06-21 fix:** `ensure_index` mapping now also declares `closetId`/`closetKind`/`imageUrl` as `keyword` (previously omitted → dynamic `text`, which broke SHARED_CLOSET `closetId` term filters and returned 0 candidates); aligned with the seed mapping. | §5.2, §8.2 |
| M2-10 | Cloud Tasks adapter (`TaskQueuePort`) | ✅ Implemented | `CloudTasksAdapter` plus async fire-and-forget `LocalHttpTaskQueueAdapter`, selected by settings; tests and smoke prove enqueue isolation and internal-worker dispatch. | §5.2, §6.8 |
| M2-11 | Flutter closet management UI | ✅ Implemented | Upload (direct MinIO/R2 PUT), list via Firestore realtime listener, delete. Implementation in `flutter-web-app/lib/closet/`: `closet_screen.dart` (grid + `users/{uid}/closet` snapshots stream + `N / 20` count), `closet_item.dart`, `thumbnail.dart` (FutureBuilder on the new signed-GET endpoint with a per-session cache), `upload_service.dart` (pick → signed PUT → complete; 429 → SnackBar), delete confirmation dialog. Backend additive endpoint `GET /closet/items/{id}/download-url` (Phase 3); `pytest -q` reports **34 passed, 1 skipped**. `flutter analyze` reports **No issues found**; `flutter test` reports **6/6 pass** (widget grid + API client). Verified 2026-06-07 in headless Chromium against `make dev`: upload via signed PUT places a PROCESSING card (amber spinner + "Analyzing…") which transitions live to READY (green badge) without polling; count goes 1 → 2; signed-URL thumbnail renders; delete drops the count to 1 / 20. | §11, ADL-015 |
| M2-12 | Firebase Security Rules (closet) | ✅ Implemented | Rules allowing per-user direct read of `users/{uid}/closet`. `firestore.rules` at repo root (owner read on `users/{uid}` and `users/{uid}/closet/*`, all client writes denied, default-deny everywhere else); `firebase.json` extended with the `firestore` block + emulator port; `@firebase/rules-unit-testing` suite at `firebase/firestore-rules.test.mjs` covers owner allow + cross-user deny + client-write deny + first-login `users/{uid}` create + unauth deny. Verified 2026-06-06: `firebase emulators:exec --only firestore --project gen-fashion-local "npm test"` reports **7 pass / 0 fail** against the rule-enforcing emulator. | ADL-015 |

**Exit criteria:** A logged-in user uploads an image → R2 stores it → Firestore metadata reaches `status: READY` → ES indexed; delete removes all three. *(The backend ExecPlan proves this at the API layer via `make dev` + a scripted curl flow; the Flutter client that drives it is the deferred follow-up plan.)*

---

## M3 — Shared Demo Closet

**Scope:** Provide a pre-seeded, read-only shared closet so first-time users can try coordination without uploading. Reference: `req-phase01.md` §16, ADL-010.

> **ExecPlan (2026-06-09):** [20260609-m3-shared-demo-closet.md](plans/20260609-m3-shared-demo-closet.md) covers all four M3 requirements. Built against **local infra now** (keyword-first, runnable subset); per the **M1-3** re-scope the full vector seed on the GCE-hosted Elasticsearch is a **deployment-phase re-run** of the same script (`--with-embeddings`). **2026-06-24 hardening:** the local subset is now 210 items (70/70/70), with the original 150 retained and 10 tops + 10 bottoms appended per closet. Firestore emulator state is imported from/exported to `gen-fashion_firestore-data`, so normal container launches do not reseed.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M3-1 | `run_seed.py` seeding script | ✅ Done | `scripts/seed_shared_closet/run_seed.py` — Kaggle download → sample → R2 upload → embed → ES index → Firestore write. Idempotent (`item_id = uuid5(filename)`); `--purge`, `--source-dir`, `--with-embeddings` flags; self-contained per §16.4. | §16.4, §15 Phase 1a #7 |
| M3-2 | `shared_closet` data populated | ✅ Implemented (local subset) | Seeds **3 realistic demo closets** (Adult×2 + Child×1, 70 items each = 210), segmented by `kids`. The stable 50-item base is selected first, then each closet appends 10 tops + 10 bottoms; all 210 images are unique. Incremental live seed retained 150 and created 60 with zero errors. ES/Firestore/MinIO contain 70/70/70; recreating Firestore restored all 210 from `gen-fashion_firestore-data` without reseeding. **Full vector seed (`--with-embeddings`) on GCE ES remains deployment-deferred (M1-3).** | §16, §8.1/§8.2, ADL-010 |
| M3-3 | `SharedClosetSearchAdapter` | ✅ Done | `ClothingSearchPort` impl filtering ES by `user_id: "__shared__"`; keyword-first search requires a keyword match for non-empty queries; returns signed shared image URLs; sets `attribution = "Clothing Dataset (CC BY-SA 4.0)"`. Own ES client (M2-9 repo untouched). | §5.2, §6.3, ADL-010 |
| M3-4 | Attribution display (CC BY-SA 4.0) | ✅ Done | `CandidateItem.attribution` set in adapter; `flutter-web-app/lib/shared/attribution.dart` — `AttributionFooter` widget + `showSharedClosetAboutDialog` wired into closet screen. `flutter analyze` clean. Per-candidate-card display is M5 handoff. | §16.3 |

**Exit criteria:** Seeding script runs idempotently; `SHARED_CLOSET` source returns candidate items with attribution.

---

## M4 — ADK Agents Core

**Scope:** Implement the agent topology and tools; runnable locally on ADK Web UI. Reference: `req-phase01.md` §6.1–6.5, §7.

> **ExecPlan (2026-06-09, completed 2026-06-11):** [20260609-m4-adk-agents-core.md](plans/20260609-m4-adk-agents-core.md) covers the **whole M4 milestone** — the nine requirements M4-1…M4-9 — and is the critical path to M5. **All nine rows → ✅** (acceptance evidence in the ExecPlan's Artifacts; the only stated limitation is that the Nano Banana generation path was exercised via its collage fallback locally — free-tier key has no `gemini-2.5-flash-image` quota). The plan's load-bearing decision: **`adk-agent-service` is rebuilt in Python ADK**, replacing the current TypeScript skeleton (recorded as **ADL-022** in `req-phase01.md`; forced by req §2, the Python M1-4 PoC `runner.run_async()`, ADL-021's shared `FirestoreStyleSessionRepository`, and reuse of the existing Python Gemini/ES/image-gen adapters). M4 stops at "runs on the ADK Web UI and each tool is callable end-to-end"; the FastAPI session routes, the Firestore `agentEvents` relay (ADL-011/ADL-021), SSE, and the Flutter Accordion/A2UI result UI are **M5**. A2UI agent-side output (ADL-018) is deferred to M5's result UI.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M4-1 | `StylingOrchestratorAgent` | ✅ Implemented | Production propose runs `runner.run_async` with the orchestrator and native ADK sub-agent delegation; the phase-specific tree physically omits generation. Recovery verified live with `transfer_to_agent` events. | §7.1 |
| M4-2 | `ClosetAgent` | ✅ Implemented | Production propose delegates to ClosetAgent, which authored three concrete garment descriptions and called `search_closet` per type in both adult/child live smokes. | §7.1 |
| M4-3 | `StylingAgent` | ✅ Implemented | Production generate starts a generation-enabled StylingAgent only after explicit selection. **Hardened 2026-06-22:** its constrained `style_synthesizer` exposes only optional style text; the server binds authenticated user, ordered selected URLs, gender, and age, and normalizes the trace/result to the effective values. ADK 41 passed; strict adult/child smokes completed. | §7.1 |
| M4-4 | Tool Registry pattern | ✅ Implemented | Each tool an independent module registered via a registry (`styling_app/tools/registry.py`); agents pull toolsets by name (ADL-019). | §7.2 |
| M4-5 | `analyze_clothing_image` tool | ✅ Implemented | Gemini structured-output image analysis; reuses the M2-5 response schema verbatim. Backs `AnalyzeClothingImageUseCase`. | §6.1, §7.2 |
| M4-6 | `search_closet` tool | ✅ Implemented | Hybrid search over ES (closet + shared closet). Keyword-first (tokenized case-insensitive terms over tags/category/colors/season) + additive fail-soft kNN (M1-3); `SHARED_CLOSET` results carry CC BY-SA 4.0 attribution + signed image URLs. | §6.3, §7.2, §8.3 |
| M4-7 | `style_synthesizer` tool | ✅ Implemented | Final coordinate image generation via Nano Banana (`gemini-2.5-flash-image`, M1-2); collage fallback (ADL-005) verified live; result stored in R2/MinIO under `{user_id}/coordinates/{uuid}.jpg`. | §6.5, §7.2 |
| M4-8 | `ask_preference` tool | ✅ Implemented | Normalizes/echoes the pre-session-form `UserPreference` (Web, §6.4). LINE interactive variant deferred to M6. | §6.4, §7.2 |
| M4-9 | `AGENT_MODEL` override | ✅ Implemented | All agents default to `gemini-2.0-flash`, overridable via `AGENT_MODEL` env var (exercised live: free-tier quota required overriding to `gemini-2.5-flash(-lite)`). | §7.1, §12.2 |

**Exit criteria:** Orchestrator + sub-agents run on local ADK Web UI; each tool callable end-to-end (§15 Phase 1a #1).

---

## M5 — Coordination Flow & Accordion UI (Web E2E)

**Scope:** Wire the full Web GUI coordination flow with live agent-thinking visualization. Reference: `req-phase01.md` §6.1–6.5, §6.11, §8.1, §11, ADL-009, ADL-011.

> **ExecPlan (2026-06-12, completed 2026-06-14):** [20260612-m5-coordination-flow-accordion-ui.md](plans/20260612-m5-coordination-flow-accordion-ui.md) covers the whole M5 milestone — M5-1…M5-11 — as one implementation slice. The selected path reuses the existing M2 closet upload pipeline, creates/updates sessions in FastAPI, starts the Python ADK service through direct HTTP after source selection (ADL-020), lets `adk-agent-service` write session state and `agentEvents` to Firestore (ADL-021), streams those events through FastAPI SSE (ADL-011), and renders them in the Flutter Accordion/result UI. Browser E2E passed on 2026-06-14. Review hardening on 2026-06-14 added final SSE drain, cursor-based event reads, source-trigger failure compensation to `ERROR`, `X-Internal-Secret` on ADK `/internal/run-session`, selected `sharedClosetId` filtering in `search_closet`, and ADK status sequencing aligned with the FastAPI state machine. Remaining caveat: Flutter Web currently uses `package:http`; the backend streams incrementally, but true browser-progressive UI should move the Web client to fetch-stream/EventSource-compatible transport.
>
> **2026-06-21 audit:** the §15 Phase 1a #6 *selection* step (候補提示 → **選択** → 画像生成) and req §3's no-auto-generation rule ("同意なき自動生成禁止") are **not** implemented — `StylingAgent` auto-calls `style_synthesizer` with no user-approval gate, and the `PROPOSING` state never pauses for input. **M5-6/M5-11's "§15 #6 satisfied" is therefore overstated**: the end-to-end flow runs, but without the mandatory candidate result UI + selection gate (the ADL-018 result UI was deferred at M5 and never built). This gap is tracked as **ME-6** (and the trace-curation half as ME-5).

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| M5-1 | `CreateSessionUseCase` | ✅ Implemented | `POST /sessions` creates `sessions/{id}` with `status: SOURCE_SELECTING`; verified by route tests, API smoke, and browser E2E. | §6.11, ADL-015 |
| M5-2 | `FirestoreStyleSessionRepository` | ✅ Implemented | Persists session state, events, style results, and state transitions; event streaming reads `seq > last_seq` instead of re-reading the whole subcollection; verified by adapter tests and E2E session docs/events. | §5.2, §8.1 |
| M5-3 | `SelectClothingSourceUseCase` | ✅ Implemented | Updates source/preference and triggers ADK execution; failed trigger attempts compensate the persisted session to `ERROR`; verified by source route/use-case tests and `SHARED_CLOSET` browser E2E. | §6.2, §4.3 |
| M5-4 | `AnalyzeClothingImageUseCase` | ✅ Implemented | Compatibility use case no longer raises M5 stubs; image intake reuses the implemented M2 closet upload path. | §6.1 |
| M5-5 | `SearchCandidateItemsUseCase` | ✅ Implemented | Implemented via ADK/shared closet search path; top/bottom category aliases and `sharedClosetId` filtering support seeded shared data. | §6.3, ADL-008 |
| M5-6 | `GenerateCoordinateUseCase` | ✅ Implemented | Implemented by the post-selection StylingAgent run; ME-6 requires explicit selected items before the generation-enabled agent exists. API/browser E2E confirmed real Nano Banana output (`gemini-2.5-flash-image`). | §6.5, §4.3 |
| M5-7 | Session lifecycle & timeout | ✅ Implemented | Local run completion/error/timeout fallback implemented and verified by tests plus browser E2E. | §4.3, ADL-009 |
| M5-8 | ADK → Firestore event relay | ✅ Implemented | Both production phases normalize actual `runner.run_async` events into monotonically sequenced Firestore `agentEvents`; live evidence includes native delegation, model-authored search calls, and the StylingAgent synthesis call. | ADL-011 |
| M5-9 | SSE streaming endpoint | ✅ Implemented | `GET /sessions/{id}/stream` backfills/polls events, performs a final drain before terminal status, and bounds stream duration; API and browser E2E completed through SSE. | §15 Phase 1a #2, ADL-011 |
| M5-10 | Flutter Accordion UI | ✅ Implemented | Coordination tab renders Accordion trace and result panel; browser E2E observed rendered completion. Caveat: Web client transport should move off XHR-backed `package:http` for true per-event progressive rendering. | §11, §15 Phase 1a #3 |
| M5-11 | Web coordination flow E2E | ✅ Implemented | ME completion E2E now covers the full required flow: candidates → explicit selection → generation → `COMPLETED`, with tool events and result image. | §15 Phase 1a #6 |

**Exit criteria:** Full Phase 1a flow works end-to-end in the browser with live Accordion UI; `shared_closet` source produces a generated coordinate image.

---

## ME — Pre-Deployment Experience & Domain Hardening

**Scope:** Close the six user-facing / domain gaps found while auditing the local build before starting **MD** (`ToDo` §1–6). **Order:** runs after M5 and **before MD**; MD must not start until the must-fix subset (**ME-3**, **ME-6** — both requirement violations) is closed. Reference: `req-phase01.md` §3, §6.2/§6.3/§6.4/§6.5, §11, §15 Phase 1a #6, §16, §8.1/§8.2, ADL-010, ADL-018.

> **ExecPlan (2026-06-21):** [20260621-me-pre-deployment-experience-domain-hardening.md](plans/20260621-me-pre-deployment-experience-domain-hardening.md) covers **ME-1…ME-6** (ME-7 deferred — its weather/duplication-avoidance is Phase-1a-out-of-scope per req §18.5 / ADL-029, and the basic history list is the most independent slice, planned as a post-MD follow-up). **MD is paused to do ME first**, as the `ToDo` file frames it and as this milestone note anticipated. Per the ExecPlan rule, **ME-2…ME-6 → 🟡 In progress** in this change (ME-1 was already 🟡; ME-7 stays ❌). The plan is structured into five implementation milestones: A (gender foundation: ME-2/ME-4), B (mandatory candidate-selection gate: ME-6, must-fix), C (gender propagation & child imagery: ME-3, must-fix), D (trace curation + result-UI split: ME-5), E (closet gallery + editable metadata: ME-1). Source-of-truth basis (synced 2026-06-21): **§18** (18.1 gender/age · 18.2 mandatory candidate selection · 18.3 closet gallery + editable metadata · 18.4 trace curation / result-UI split · 18.5 run history) plus **ADL-026** (gender/age dimension), **ADL-027** (PROPOSING-as-paused-state selection gate), **ADL-028** (user-editable closet metadata, own items only), **ADL-029** (run history; weather/duplication = future), with targeted edits to §4.2/§4.3, §6.4/§6.5, §8.1/§8.2 (`gender` field), §11, §15 #6, §16. **Gender decision:** heuristic by category (`Dress`/`Skirt`/`Blouse` → `female`, else `common`; `male` user-set only), user-editable in the gallery for own items (ADL-026/ADL-028). The selection gate is implemented as a **two-phase ADK run** (propose → pause at `PROPOSING` → user `POST /sessions/{id}/select` → generate). `docs/architecture-overview.md` is updated in this same change with the ME-planned additions (`POST /sessions/{id}/select` + `session.proposed` SSE + `proposedCandidates`, `GET /shared-closets[/{id}/items]`, `PATCH /closet/items/{id}`, `gender` across the data plane, two-phase run).

> **Completion (2026-06-21):** ME-1…ME-6 are implemented and verified; both
> must-fix gates are closed. **2026-06-24 follow-up:** ME-7's basic gallery is
> also implemented; MD is no longer blocked by ME.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| ME-1 | Closet gallery view (own + shared) with metadata | ✅ Implemented | Authenticated `GET /shared-closets[/{id}/items]` endpoints and a Flutter Shared tab browse all three demo closets. Own cards show richer metadata and an edit dialog calls owner-only `PATCH /closet/items/{id}`, mirrored to ES. Shared data is now 70/70/70 and its Firestore catalog survives container recreation through `gen-fashion_firestore-data`. | §18.3, §11, §16, ADL-028 |
| ME-2 | Gender/age dimension in domain + preference form | ✅ Implemented | `UserPreference.gender` (`male`/`female`/`common`) is collected by Flutter, persisted in sessions, and passed to both run phases. | §18.1, §4.2, §6.4, ADL-026 |
| ME-3 | Gender/age propagation to search, styling & image generation | ✅ Implemented · **must-fix closed** | Search fail-soft-biases gender; generation now binds resolved gender/closet kind server-side, so the model cannot override them. Strict child session `5a0a5fdd-…` persisted `child female wearer`; image generation used collage fallback in this verification, while prior session `0adfd256-…` remains the real-model visual-child evidence. | §18.1, §6.3, §6.5, §4.3, ADL-026 |
| ME-4 | Shared-closet gender data (male/female/common) | ✅ Implemented | Seed and own-item analysis apply the category heuristic; Firestore and ES persist gender (`keyword`). Local seed: 210 docs, 70/70/70. | §18.1, §16.1, §8.1/§8.2, ADL-026 |
| ME-5 | Agent-Trace curation (thinking trace only) | ✅ Implemented | Actual ADK delegation/tool/model events are normalized; the synthetic action-derived transfer duplicate remains suppressed. Flutter uses concise summaries with raw detail only on expansion, while candidates/results render in dedicated panels. | §18.4, §11, ADL-018 |
| ME-6 | Candidate result UI + mandatory user-selection gate | ✅ Implemented · **must-fix closed** | The propose tree structurally withholds generation and `/select` remains mandatory. The generate tool now binds the server-held selected URLs in order and normalizes `styleResult`; incomplete selected items fail before Runner start. Strict adult `9d09807b-…` and child `5a0a5fdd-…` smokes verified exact URL/user matches. | §18.2, §3, §15 #6, ADL-027, ADL-018 |
| ME-7 | Agent run history (time-series gallery) | ✅ Implemented | ADK writes authoritative `completedAt`; authenticated `GET /sessions` filters by owner + `COMPLETED`, orders newest first, and supports a bounded `limit`; Flutter History shows the generated image, date, source, and selected garments. The Firestore composite index is declared. Weather signals, recent-wear **duplication avoidance**, retries, and cursor pagination remain future scope. | §18.5, §11, ADL-029 |

**Exit criteria:** Closed: `child-01` generation is child-aware (ME-3); generation requires explicit candidate selection (ME-6); shared closets are browsable with gender-tagged metadata (ME-1/ME-4); the Agent Trace is separated from candidate/result UI (ME-5); and completed runs are browsable in the owner-scoped History gallery (ME-7). Weather/deduplication extensions remain future work.

---

## MD — Phase 1a Production Deployment & Hardening

**Scope:** Deploy the locally-verified Phase 1a stack (M0–M5) to Google Cloud and complete the work the requirements defer to "the deployment phase." Reference: `req-phase01.md` §9.1, §9.2, §9.3, §12.1, §12.2, §15 Phase 1a #6/#7, §16.4, ADL-005, ADL-010, ADL-012, ADL-013, ADL-014, ADL-016, ADL-021, ADL-023, ADL-024, ADL-025.

> **Progress update (2026-06-27): MD resumed (ME complete); Milestone 0 + Milestone A landed.** Deploy-readiness patch (Milestone 0) and the GCP foundation (Milestone A) are done on project `animation-agent` / `asia-northeast1`: **MD-1 ✅** (APIs, 3 service accounts + IAM, Firestore + rules/indexes, Firebase + Google sign-in + Web app) and **MD-9 ✅** (R2 bucket + CORS + keys in Secret Manager); **MD-2 still 🟡** (R2 + internal secrets stored, but `ELASTICSEARCH_API_KEY` and Cloud Run env config remain). Next: **Milestone B** (Compute Engine ES, Cloud Run **Direct VPC egress** private connectivity, full vector seed — MD-3/MD-4/MD-10). **2026-06-27 cost re-scope (ADL-023):** Milestone B switched from a Serverless VPC Access connector to **Direct VPC egress** (no idle connector fixed fee, same closed-network posture); ES VM uses **`pd-balanced` + static internal IP**, stopped when idle, with an optional `Asia/Tokyo` night-stop instance schedule for the post-submission window.
>
> **ExecPlan (2026-06-15):** [20260615-md-phase1a-production-deployment.md](plans/20260615-md-phase1a-production-deployment.md) covers the whole MD milestone (MD-1…MD-14). All rows → 🟡 In progress. The plan is provisioning + configuration heavy because the code is already env-driven; the only application changes are four minimal `fastapi-service` edits (split the conflated `ADK_INTERNAL_BASE_URL` so the `process-upload` worker task targets the fastapi URL via a new `FASTAPI_INTERNAL_BASE_URL`; attach OIDC identity tokens on both internal hops; verify the OIDC bearer on the worker route). MD completes M1-3 (GCE ES + private connectivity), the M3-2 full **vector** seed, the M2-5 production security gate, and the M4-7/M5-6 Nano Banana caveat. **Independent of M6 (LINE, Phase 1b) — LINE work does not start here (`req-phase01.md` §14).** **2026-06-21: MD is now gated on milestone [ME](#me--pre-deployment-experience--domain-hardening) and is PAUSED while ME runs.** The ME ExecPlan ([20260621-me-pre-deployment-experience-domain-hardening.md](plans/20260621-me-pre-deployment-experience-domain-hardening.md), ME-1…ME-6) is the active ExecPlan; MD resumes once ME's must-fix subset is closed — the `child-01` → adult-image defect (**ME-3**) and the missing mandatory user-selection step (**ME-6**), both requirement violations. The rest of ME (closet gallery, full gender data, trace curation) is strongly recommended pre-deploy; ME-7 (run history) is deferred to a post-MD plan.

> **ME gate update (2026-06-21):** ME-3 and ME-6 are closed; MD may resume.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MD-1 | GCP project & IAM foundation | ✅ Implemented | **2026-06-27 (Milestone A):** project `animation-agent`; enabled 11 core APIs + Firebase Management/Hosting/Identity Toolkit; created `fastapi-sa`/`adk-sa`/`tasks-invoker-sa` with least-privilege roles (+ `fastapi-sa`→`tasks-invoker-sa` `serviceAccountUser`); Firestore Native `asia-northeast1` created with `firestore.rules`+`firestore.indexes.json` deployed; Firebase added (console, ToS accepted), Google sign-in enabled, Web app `gen-fashion-web` registered. | §9.1, §12.1, ADL-012 |
| MD-2 | Secret Manager + config split | 🟡 In progress | Store `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `ELASTICSEARCH_API_KEY`, `INTERNAL_TASK_SECRET` in Secret Manager; non-secret config via `--set-env-vars`; app reads both uniformly as env vars. **2026-06-27 (Milestone A):** `INTERNAL_TASK_SECRET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` stored; `fastapi-sa`/`adk-sa` granted `secretmanager.secretAccessor`. **Remaining:** `ELASTICSEARCH_API_KEY` (minted in MD-3/Milestone B) and `--set-env-vars` config applied at Cloud Run deploy (Milestone C). | §12.1, §12.2, ADL-012 |
| MD-3 | Compute Engine Elasticsearch node | 🟡 In progress | Provision `e2-medium` VM (no external IP, **30 GB `pd-balanced`**, **static internal IP**) in `asia-northeast1-a`; install ES 8.x with `xpack.security` enabled + API key; systemd auto-start; firewall `tcp:9200` from the **Cloud Run Direct VPC egress subnet range** only. **Cost (ADL-023):** `pd-balanced` not SSD; stop the VM when idle; optional `Asia/Tokyo` night-stop instance schedule. Completes the GCE half of M1-3. | §9.2, ADL-013, ADL-023 |
| MD-4 | Cloud Run ↔ ES private connectivity | 🟡 In progress | **Direct VPC egress** (`--network`/`--subnet` + `--vpc-egress=private-ranges-only`, no Serverless VPC Access connector — ADL-023); verify Cloud Run reaches ES privately via the VM's static internal IP; record JP-analyzer not required. Closes the M1-3 PoC question. | §9.2, ADL-013, ADL-023, §17 |
| MD-5 | Artifact Registry images | 🟡 In progress | Create Docker repo; build/push `fastapi-service` and `adk-agent-service` images via Cloud Build. | §9.1 |
| MD-6 | Deploy `fastapi-service` (Cloud Run) | 🟡 In progress | Public ingress, min 0 / max 10, 1 GB / 1 CPU / 60 s; env + secrets + `fastapi-sa`; `TASK_QUEUE_MODE=cloud_tasks`; wired to ADK + own worker URL. | §9.1, ADL-016 |
| MD-7 | Deploy `adk-agent-service` (Cloud Run) | 🟡 In progress | Private (`--no-allow-unauthenticated`), min 1 / max 5, 2 GB / 1 CPU / 600 s; `GOOGLE_GENAI_USE_VERTEXAI=true`; only `fastapi-sa` holds `run.invoker`. | §9.1, ADL-016 |
| MD-8 | Cloud Tasks queue + OIDC hardening | 🟡 In progress | Create `gen-fashion-embed` queue; split the conflated internal base URL (`FASTAPI_INTERNAL_BASE_URL` for `process-upload`, `ADK_INTERNAL_BASE_URL` for run-session); attach OIDC tokens on both internal hops; verify the OIDC bearer (+ shared secret) on the worker route. Completes the M2-5 deploy gate. **2026-06-21: the base-URL split landed early during local re-verification** (`fastapi_internal_base_url` in `config.py` + `local_task_queue.py`; `FASTAPI_INTERNAL_BASE_URL` in `docker-compose.yml`) — it was a live `make dev` bug, not just a cloud one. **Still open:** the Cloud Tasks `oidc_token`/audience, the `adk_agent_run.py` OIDC ID token, and worker-route OIDC bearer verification. | §6.8, §10.3, ADL-024 |
| MD-9 | Production R2 bucket + CORS | ✅ Implemented | **2026-06-27 (Milestone A):** Cloudflare R2 bucket `gen-fashion-images` created (Public access OFF — all access via S3 presigned URLs); CORS allows `GET/PUT/POST` from `https://animation-agent.web.app`, `https://animation-agent.firebaseapp.com`, `https://localhost:8080`; R2 API-token keys stored in Secret Manager (`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`). | §8.4, ADL-014 |
| MD-10 | Full vector seed to production | 🟡 In progress | Run `run_seed.py --with-embeddings` from inside the VPC against prod R2/ES/Firestore; verify 768-dim embeddings + hybrid/kNN search; idempotent re-run. Completes the M3-2 deployment portion. **2026-06-21 de-risked locally:** embedding model corrected to `gemini-embedding-001` and switched to **text** embeddings (category/colors/tags/season) so index + query share one space; local `--with-embeddings` seeded 90×768-dim vectors and kNN returns relevant hits. Remaining for deploy: run against prod ES with prod project (where Vertex == Firestore project, so the local project-split is a no-op). | §15 Phase 1a #7, §16.4, ADL-010 |
| MD-11 | Production Nano Banana image gen | 🟡 In progress | Confirm `style_synthesizer` produces a real generated image (not collage) on Vertex AI with billing; adjust `GOOGLE_CLOUD_LOCATION` to a model-available region. Resolves the M4-7/M5-6 caveat. | §6.5, ADL-005 |
| MD-12 | Flutter Web build + Firebase Hosting | 🟡 In progress | `flutter build web --release` with production `--dart-define`s (`USE_EMULATORS=false`, real `FIREBASE_*`, `API_BASE_URL`=fastapi URL); deploy to Firebase Hosting; authorized domains + CORS allowlist. | §11, ADL-025 |
| MD-13 | Production E2E smoke | 🟡 In progress | Authenticated `SHARED_CLOSET` session reaches `COMPLETED` with a generated image, via the hosted SPA and the adapted API smoke against deployed URLs. | §15 Phase 1a #6 |
| MD-14 | Logging, TTL & teardown | 🟡 In progress | Verify ADK event stream queryable in Cloud Logging; ensure `agentEvents.ttlAt` TTL (24 h) policy active; commit/dry-run `scripts/deploy/teardown.sh`. | §9.3, ADL-021 |

**Exit criteria:** Opening the public Firebase Hosting URL and completing a `SHARED_CLOSET` coordination to a generated image works against deployed infrastructure (`req-phase01.md` §15 Phase 1a #6 satisfied in the cloud); all secrets live in Secret Manager; ES is reachable only privately; a documented teardown can dismantle the throwaway environment.

---

## MF — CI/CD (Continuous Delivery)

**Scope:** Automate the manual deployment MD performs by hand, and add the test gate the repo currently lacks. This is the hackathon's **CI/CD-after-deployment** axis. Built on GitHub Actions with keyless **Workload Identity Federation**; CD is a thin wrapper over MD's `scripts/deploy/deploy_*.sh`. **Depends on MD** (the deploy commands/scripts must exist first). Reference: `req-phase01.md` §19, ADL-030 / ADL-031 / ADL-032.

> **Tracking only (2026-06-26):** rows added at the requirements level; **no ExecPlan authored yet** per "one ExecPlan at a time" (MD is the resume-next milestone). The CI/CD ExecPlan is authored after MD completes. No CI/CD assets exist in the repo today (`.github/`, Cloud Build trigger, `cloudbuild.yaml`, `scripts/deploy/` are all absent). Subagent fan-out for execution (audit per-service test/build entrypoints → author CI workflow → author CD workflow + WIF → smoke/rollback → runbook+sync) is defined in the planning discussion and runs when the ExecPlan is authored.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MF-1 | Workload Identity Federation | ❌ Not yet implemented | Create the Workload Identity Pool/Provider; federate GitHub Actions OIDC to a `github-deployer` SA (no JSON key); bind by repo+branch; grant `run.admin` / `artifactregistry.writer` / `iam.serviceAccountUser` / `firebasehosting.admin`. | §19.1, ADL-030 |
| MF-2 | CI gate (tests + build) | ❌ Not yet implemented | On PR + push to `main`, parallel jobs: fastapi `pytest` (68), adk `pytest` (41), flutter `analyze`+`test` (14), and Docker build validation of both images. Integration tests needing Firestore Emulator / ES use service containers or are scoped to unit. All green = merge gate. | §19.2, ADL-031 |
| MF-3 | CD — backend (Cloud Run) | ❌ Not yet implemented | On `main` merge, build/push both images to Artifact Registry and deploy both Cloud Run services by calling MD's `scripts/deploy/deploy_*.sh`; env via `--set-env-vars`, secrets via `--set-secrets`. | §19.3, ADL-032 |
| MF-4 | CD — frontend (Firebase Hosting) | ❌ Not yet implemented | On `main` merge, `flutter build web --release` with production `--dart-define`s and `firebase deploy --only hosting`; reuse MD-9/MD-12 authorized-domains + R2 CORS config. | §19.3, ADL-032, ADL-025 |
| MF-5 | Post-deploy smoke + rollback | ❌ Not yet implemented | After deploy, run `GET /health` + an authenticated coordination smoke against the deployed URL (`scripts/m5_coordination_smoke.py` adapted) to `COMPLETED`; on failure, roll back Cloud Run traffic to the previous revision. | §19.4, ADL-032 |
| MF-6 | Pipeline runbook + matrix sync | ❌ Not yet implemented | Document triggers, required IAM, rollback, and secret handling; keep MF-* rows and the CI/CD ExecPlan in sync per the repo's sync rule. | §19.5 |

**Exit criteria:** A merge to `main` builds, deploys both Cloud Run services and Firebase Hosting via WIF (no stored keys), runs a post-deploy smoke to `COMPLETED`, and rolls back automatically on smoke failure — with the CI gate blocking merges whose tests fail.

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
