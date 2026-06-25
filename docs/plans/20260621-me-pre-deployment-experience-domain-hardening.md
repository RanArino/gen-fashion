# ME — Pre-Deployment Experience & Domain Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


Before the Phase 1a stack is deployed to Google Cloud (the **MD** ExecPlan,
`docs/plans/20260615-md-phase1a-production-deployment.md`), a pre-deployment
audit of the locally-running build found six user-facing / domain gaps,
recorded in the repo's `ToDo` file and tracked as feature-matrix rows
**ME-1…ME-7** (`docs/feature-matrix-phase01.md`). Two of them are outright
**requirement violations** and are the gate that MD must not cross:

- **ME-3 (defect):** selecting the child demo closet (`child-01`) still
  generates an *adult* coordinate image. The seed tags items `closetKind="child"`
  but that signal is never propagated to search, styling, or image generation.
- **ME-6 (requirement violation):** `req-phase01.md` §3 forbids generating a
  coordinate without the user first selecting clothes ("同意なき自動生成禁止"),
  and §15 Phase 1a #6 requires the flow "候補提示 → **選択** → 画像生成". Today
  `StylingAgent` auto-calls `style_synthesizer`; the `PROPOSING` state never
  pauses for the user.

After this plan, a user gains:

- A **gender/age-correct** experience: a gender selector (male / female / common)
  in the pre-session form, threaded — together with the closet's adult/child kind
  — into search, the styling prompt, and image generation, so `child-01`
  produces child imagery and the chosen gender biases results (ME-2/ME-3/ME-4).
- A **mandatory candidate-selection step**: after search, the session pauses,
  the searched items render as candidate cards (top-N plus a highlighted
  recommendation), and image generation runs **only after** the user confirms a
  selection (ME-6).
- A **browsable closet gallery** for their own closet and for each shared closet
  (`adult-01` / `adult-02` / `child-01`), showing per-item metadata, with their
  own items' searchable metadata (including gender) editable (ME-1).
- A **readable agent trace**: the Accordion shows a curated thinking trace, with
  candidate and result data moved into a separate result UI (ME-5, ADL-018).
- A **run-history gallery**: authenticated users can browse completed
  coordinates newest first, including the generated image, completion time, and
  selected garments (ME-7).

**Scope of this plan:** feature-matrix rows **ME-1, ME-2, ME-3, ME-4, ME-5,
ME-6, ME-7**. ME-7 was initially deferred, then reopened on 2026-06-24 for its
basic independent slice. Weather signals, recent-wear duplication avoidance,
retry actions, and cursor pagination remain explicitly out of scope (req §18.5
/ ADL-029).

**Sequencing note:** This plan exists because MD is **paused to do ME first**, as
the `ToDo` file frames it ("Phase 1a Production Deployment & Hardening を実行する
前にやるべきことがあります") and as the feature matrix's ME milestone note
anticipated. MD resumes once this plan's must-fix subset (ME-3, ME-6) is closed.


## Progress


- [x] (2026-06-24 11:20Z–11:32Z) ME-7 follow-up — Implemented the authenticated
  completed-session API and Flutter run-history gallery, with `completedAt`
  persistence, a required Firestore composite index, and focused backend/frontend
  tests. Full verification: FastAPI 68 passed, ADK 41 passed, Flutter analyze
  clean / 14 tests passed. Live smoke session `a86d94c8-…` reached `COMPLETED`
  and appeared in `GET /sessions` with a server timestamp and generated image.
  Weather signals, wear-history deduplication, retries, and pagination remain
  out of scope.
- [x] (2026-06-21 07:08Z) Milestone A — Added the gender dimension to the
  domain, session/closet persistence, ES mappings/indexing, upload analysis,
  and the shared seed (ME-2 + ME-4).
- [x] (2026-06-21 07:11Z) Milestone B — Added the explicit propose/select/generate
  gate, `session.proposed` SSE event, candidate cards, and selection-triggered
  generation (ME-6, must-fix).
- [x] (2026-06-21 07:12Z) Milestone C — Propagated gender and closet kind through
  search and generation; child runs now send `wearer_age=child` (ME-3, must-fix).
- [x] (2026-06-21 07:15Z) Milestone D — Removed the synthetic action-derived
  transfer duplicate and replaced raw primary trace text with concise summaries
  while keeping candidates/results in their own panels (ME-5).
- [x] (2026-06-21 07:20Z) Milestone E — Added authenticated shared-gallery reads,
  a Flutter gallery, and owner-only metadata editing mirrored to ES (ME-1).
- [x] (2026-06-21 07:24Z) Full verification — FastAPI 64 passed, ADK
  29 passed, Flutter analyze clean/12 tests passed, seed 90/90, two-step adult
  and child API smokes completed, and rendered browser E2E completed session
  `b3555338-2a87-467a-ab0c-8dc27fa6b7b7`.
- [x] (2026-06-21 09:47Z–10:10Z) Emergency agent-flow recovery — Reopened after code
  review confirmed that production `/internal/run-session` no longer invokes
  `Runner.run_async`, `root_agent`, or `normalize_adk_event`; restore two real
  ADK runs while retaining the explicit selection gate and all ME-1…ME-6 work.
  - [x] (2026-06-21 09:52Z) Added phase-specific agent composition, restored
    `runner.run_async` and normalized-event persistence in both phases, limited
    deterministic operations to zero-result fallbacks, and added structural
    gate/runner/propagation tests. ADK suite: 36 passed.
  - [x] (2026-06-21 10:10Z) FastAPI 64 passed; ADK 36 passed; Flutter analyze
    clean/12 passed. Strict primary-agent smokes completed adult session
    `02ea5e0b-…` and child session `0adfd256-…`; the latter produced a visually
    confirmed child image with the real image model. Rendered browser session
    `268d9a09-…` completed with one transfer, three searches, one synthesis, and
    zero fallback events. Gallery probe returned 3 closets/30 child items/0
    missing gender. Feature matrix and architecture overview were synchronized.
- [x] (2026-06-21 22:32Z–22:39Z) Generate-phase authority hardening (review #1
  + #3) — Bound `user_id`, ordered selected image URLs, `gender`, and
  `wearer_age` in a phase-local generation tool; normalized trace/result values;
  and added omission/substitution/missing-image tests. ADK 41, FastAPI 64,
  Flutter analyze clean/12 tests, and diff checks passed. Strict two-step smokes
  completed adult session `9d09807b-…` and child session `5a0a5fdd-…` with exact
  ordered selected-URL and authenticated-user matches. Adult used the real image
  model; three child attempts reached `COMPLETED` through collage fallback, while
  the persisted tool result proved the effective prompt contained
  `child female wearer`.
- [x] (2026-06-23 23:28Z–23:36Z) Shared-closet persistence and capacity
  hardening — Expanded all three demo closets to 50 items with kind-specific
  quotas (150 unique images total), fixed `make seed` to purge then reseed, and
  persisted the Firestore emulator snapshot in the named
  `gen-fashion_firestore-data` volume. Live seed created 150 with zero errors;
  deleting and recreating the Firestore container restored 3 metadata docs and
  all 150 item docs without rerunning the seed. Shared-search adapter tests
  remained green (8 passed), seed compilation and Compose config validation
  passed, and `git diff --check` was clean.
- [x] (2026-06-24 11:47Z–11:51Z) Shared-closet separates expansion — Preserved
  each existing 50-item wardrobe, then appended 10 tops and 10 bottoms to every
  closet. The dataset had sufficient child inventory, so all three reached 70
  items (210 unique images total). Incremental live seed reported 150 skipped,
  60 created, and zero errors. ES, Firestore, and MinIO each contain 210 items;
  recreating Firestore imported 70/70/70 from `gen-fashion_firestore-data`
  without another seed run.


## Surprises & Discoveries


- Observation: Filtering completed sessions by both `userId` and `status` while
  sorting by `completedAt` requires a Firestore composite index; automatic
  single-field indexes are insufficient. Evidence: the query shape in
  `FirestoreStylingRepository.list_completed` and the Firebase Standard index
  rules. Implication: `firestore.indexes.json` and its `firebase.json` binding
  are part of ME-7, not optional deployment follow-up.

- Observation: The ADK test virtualenv does not contain `google-cloud-firestore`
  even though production requirements declare it. Evidence: a top-level import
  failed test collection with `ModuleNotFoundError: google.cloud`. Implication:
  keep the adapter's established lazy-import pattern and isolate the
  `SERVER_TIMESTAMP` lookup behind a tiny helper that fake-client tests replace.

- Observation: The current coordination run is a single fire-and-forget ADK
  background task that goes search → propose → generate → `COMPLETED` with no
  pause point. The `PROPOSING` state exists in the state machine and the status
  writer, but the run only passes *through* it (it bumps `PROPOSING` then
  immediately `GENERATING` when it sees a `style_synthesizer` tool call).
  Evidence: `adk-agent-service/styling_app/server.py` `execute_run_session`
  (lines 126–169) and `_run_deterministic_fallback` (lines 175–283); the
  status-bump on `style_synthesizer` is at server.py lines 138–143.
  Implication: ME-6 is not a UI-only change — it requires splitting the run into
  a **propose phase** (stops at `PROPOSING`) and a **generate phase** (triggered
  by an explicit user selection). This is the load-bearing design in Milestone B.

- Observation: Firestore client writes to the closet are **denied by the security
  rules** (`firestore.rules` lines 13–16: closet writes are backend-only via the
  Admin SDK), and the shared-closet collections (`shared_closet`,
  `shared_closets`) are not client-readable at all (default-deny). Evidence:
  `firestore.rules`. Implication: ME-1's own-item metadata edit must go through a
  new backend endpoint (not a direct Firestore write), and the shared-closet
  gallery must read through a new backend endpoint — which is exactly what
  req §18.3 / ADL-028 specify.

- Observation: The ES `closetId`/`closetKind` keyword mapping already exists in
  both the seed (`scripts/seed_shared_closet/run_seed.py` `_ensure_es_index`) and
  the fastapi M2-9 repo (`elasticsearch_embedding_repo.py` `ensure_index`), after
  the 2026-06-21 local-verification fix. Evidence: both mappings declare
  `closetId`/`closetKind`/`imageUrl` as `keyword`. Implication: adding `gender`
  as a keyword in both places is a small, well-trodden change.

- Observation: `run_seed.py --source-dir .dataset_cache/images_original` cannot
  find the sibling cached `images.csv`, so it falls back to one 30-item adult
  closet. Running the seed without `--source-dir` hits the same cached image
  directory while also locating the CSV and builds all three 30-item closets.
  Evidence: the first run reported `total_samples: 30`; the corrected cached run
  reported `total_samples: 90` and `adult-01/adult-02/child-01: 30/30/30`.

- Observation: `--purge` deletes shared documents but does not delete the ES
  index, so a newly-added keyword mapping is not installed by purge alone.
  Evidence: the implementation uses `_delete_by_query`; the successful local
  backfill explicitly ran `DELETE /clothing_items` before reseeding, after which
  the mapping reported `gender: keyword` and `missing_gender: 0`.

- Observation: The deterministic two-phase server driver preserved the consent
  gate but removed the product's core agent behavior from the production path.
  `/internal/run-session` imports and directly invokes `search_closet` and
  `style_synthesizer`, writes scripted `ClosetAgent`/`StylingAgent` events, and
  never constructs a `Runner` or calls `normalize_adk_event`.
  Evidence: the current `server.py` has direct tool calls at `_run_search_phase`
  and `_run_generate_phase`; its diff removes `Runner`, `root_agent`,
  `runner.run_async`, and the normalization loop. The tests were also changed
  from fake-runner events to direct tool monkeypatches.
  Implication: the gate must remain two-phase, but each phase must again be a
  real ADK run. Generation safety is enforced by withholding the generation
  tool from the propose agent tree, not by replacing the agent with fixed code.

- Observation (review #1 + #3): After the agent-flow recovery, the generate
  `StylingAgent` called the registry `style_synthesizer` with **model-authored**
  `user_id`, `item_image_urls`, `gender`, and `wearer_age`. Nothing constrained
  the LLM to the actual requester, the user's explicit selection, or the
  resolved closet kind, and the persisted trace/result echoed whatever the model
  emitted. Evidence: the recovered `server.py` only post-fixed `search_closet`
  args in propose; the generate tool-call was written through unchanged, and
  `_collect_style_result` copied `items` straight from the tool response.
  Implication: authorization (who), consent target (which garments), and the
  age/gender of the depicted wearer were model-controlled, so a prompt-injected
  or hallucinated tool call could generate for the wrong user, wrong items, or
  wrong wearer. The fix moves these to server-fixed closure values and
  normalizes the saved trace/result, leaving only `style_description` to the LLM.


## Decision Log


- Decision: Implement the ME-6 selection gate by **splitting execution into two
  independent ADK runs** keyed by a `phase` field on the run request —
  `phase="propose"` (search → persist candidates → set `PROPOSING` → stop) and
  `phase="generate"` (generate from the user-selected items → `COMPLETED`). The
  `style_synthesizer` tool is **not reachable** in the propose phase, so the
  "no generation without selection" invariant (req §3) holds by construction, not
  by prompt discipline.
  Rationale: The pause is deterministic and testable because the propose agent
  tree physically lacks `style_synthesizer`; it does not rely on the LLM choosing
  to stop. This satisfies ADL-027's explicit `PROPOSING` pause while retaining
  real orchestrator/sub-agent behavior.
  Date/Author: 2026-06-21 / Claude (ME ExecPlan authoring).

- Decision: The SSE stream **closes and emits `session.proposed`** when the
  session is in `PROPOSING` **and `selectedItems` is empty** (awaiting the user).
  After `POST /sessions/{id}/select` persists a non-empty `selectedItems` and
  triggers the generate phase, the client re-opens the stream, which now streams
  through `GENERATING` to `COMPLETED`.
  Rationale: Avoids holding the SSE connection open for the full
  `STREAM_MAX_SECONDS` (150 s) human-think time, and the "selectedItems empty"
  guard makes the re-opened stream race-free (it never re-closes on `PROPOSING`).
  Date/Author: 2026-06-21 / Claude.

- Decision: Gender is a heuristic, category-based assignment, **user-correctable
  for own items only** (ADL-026 / ADL-028). The heuristic maps `Dress` / `Skirt`
  / `Blouse` → `female`; everything else → `common`; `male` is never assigned by
  the heuristic but is a valid user-set/user-preference value.
  Rationale: Matches req §18.1's stated heuristic, adds zero API cost, is
  deterministic/idempotent, and is the minimal correct default given the Kaggle
  dataset has no gender column.
  Date/Author: 2026-06-21 / Claude.

- Decision: This plan covers ME-1…ME-6 and **defers ME-7**.
  Rationale: ME-7's weather/duplication-avoidance is Phase-1a-out-of-scope
  (req §18.5 / ADL-029); the remaining history-list slice is the most independent
  and lowest-value, so it is a clean post-MD follow-up. Confirmed with the user at
  authoring time.
  Date/Author: 2026-06-21 / Claude.

- Decision: **Supersede the ME-7 deferral** and add only the basic completed-run
  gallery to this living ExecPlan.
  Rationale: The user explicitly reopened the remaining task. The minimal slice
  is independent: an authoritative `completedAt`, an owner-filtered first-page
  API (`limit` only), and a Flutter gallery. Weather, duplication avoidance,
  rerun/retry behavior, and cursor pagination remain future work exactly as
  ADL-029 requires.
  Date/Author: 2026-06-24 / User + Codex.

- Decision: **Superseded by the following decision.** Drive both coordination phases deterministically in the ADK service
  wrapper rather than running the open-ended orchestrator before fallback.
  Rationale: It is the smallest way to make `style_synthesizer` unreachable in
  propose, preserves the existing registered tools and trace schema, removes a
  duplicate LLM/fallback execution path, and keeps the consent invariant
  independent of prompt adherence.
  Date/Author: 2026-06-21 / Codex.

- Decision: **Supersede the preceding deterministic-production decision.** Run
  two independent ADK invocations separated by the existing human selection:
  propose uses an orchestrator whose complete agent tree omits
  `style_synthesizer`; generate uses a generation-enabled `StylingAgent` with
  only the explicitly selected image URLs. Deterministic search/generation
  remains phase-local fallback only.
  Rationale: This restores M4-1/M4-2/M4-3 behavior and authentic ADK event
  traces in production while preserving ME-6 structurally—the propose runner
  cannot call a tool it does not possess.
  Date/Author: 2026-06-21 / Codex.

- Decision: In the production generate phase, inject a **constrained
  `style_synthesizer` wrapper** whose only LLM-visible argument is an optional
  `style_description`. The wrapper closes over the server-fixed `user_id`, the
  ordered selected image URLs, the resolved `gender`, and the resolved
  `wearer_age`, and calls the unchanged registry tool with all arguments
  explicit. The recorded tool-call event and the persisted
  `styleResult.items`/`selectedItems` are normalized to these server values, and
  a selection missing any image URL errors the session before the Runner starts.
  Empty model `style_description` falls back to `_style_description(...)`.
  Rationale: This keeps the LLM's creative role (style wording) and the real ADK
  run/consent gate/fallback intact, while making authentication, consent target,
  and depicted-wearer age/gender structurally un-spoofable rather than reliant on
  prompt adherence. It mirrors the existing propose-phase `search_closet`
  arg-binding pattern, so it adds no new architecture. The raw `style_synthesizer`
  tool, FastAPI/Flutter API, Firestore, and ES schemas are untouched; the
  architecture-overview diagram is unchanged (no component/port/dataflow change).
  Date/Author: 2026-06-22 / Claude (review #1 + #3 follow-up).

- Decision: Preserve the existing 50-item selection pass, then append 10 tops
  and 10 bottoms per closet in a second deterministic pass. Rationale: directly
  increasing the base quotas would advance the shared adult category cursors
  before `adult-02` is built and replace existing items. The two-pass selector
  keeps all 150 prior IDs and adds only 60 unique, frequently used separates.
  Date/Author: 2026-06-24 / User + Codex.


## Outcomes & Retrospective


ME-1…ME-6 are complete. The coordination flow now pauses at `PROPOSING`, exposes
ranked candidate cards, and cannot invoke image generation until the authenticated
owner posts a non-empty selection. Gender is persisted and indexed end-to-end;
the shared seed contains 90 items with no missing gender values, and child runs
pass `wearer_age=child` to real Nano Banana generation.

Verification evidence:

- FastAPI: 64 passed (including the live ES lifecycle test).
- ADK: 36 passed. Flutter: `flutter analyze` clean; 12 tests passed; release Web
  build succeeded.
- Local seed: 90 created, 0 errors, 30 items in each shared closet; ES gender
  aggregation `common=76`, `female=14`, missing=0; Firestore 90 docs, missing=0.
- Agent recovery adult smoke: session `02ea5e0b-dbdb-4fc5-9da2-452b8f573fce`
  completed through native delegation with no deterministic search fallback.
  The LLM authored six descriptions including `white casual shirt`,
  `blue casual pants`, and `blue flats`; `gender=female` reached all searches
  and generation.
- Agent recovery child smoke: session `0adfd256-a688-4316-9c61-58a8f89277f7`
  completed without search fallback. Both LLM descriptions included child;
  synthesis received `wearer_age=child`, `gender=common`, and used
  `gemini-2.5-flash-image`. The generated 864×1184 image was visually confirmed
  to show a child (`/tmp/me-agent-recovery-child-final.jpg`).
- Authenticated gallery/edit probe: 3 closets, 30 child items, no missing gender;
  editing an own item to `female`/`formal` was reflected in ES.
- Rendered browser E2E: session `268d9a09-6db0-4424-8237-6f8295dcdd5b`
  completed with 21 streamed events, native transfer, three model-authored
  searches, synthesis, candidate selection, and a result with no fallback.
  Screenshot: `/tmp/m5-browser-e2e.png`.

ME-7 basic history is complete. ADK completion writes an authoritative Firestore
server timestamp; FastAPI maps and queries completed sessions by owner in
descending completion order; Flutter exposes a History destination with loading,
error, empty, and gallery states. The gallery shows the generated image, date,
source label, and selected-item thumbnails. A composite Firestore index is
declared for the production query. Verification: FastAPI 68 passed, ADK 41
passed, Flutter analyze clean / 14 tests passed. Live authenticated backend
smoke session `a86d94c8-9096-4110-a61c-33df70152c22` completed a real
propose→select→generate run; `GET /sessions` returned it with
`completed_at=2026-06-24T11:32:14.870000Z` and a non-empty generated-image URL.
The browser layout itself is covered by the widget test rather than a repeated
rendered-browser E2E.

Shared-closet capacity follow-up (2026-06-24): all existing 150 IDs were
retained and 60 tops/bottoms were added. The live stores now contain 210 items
(70/70/70); Firestore container recreation restored the updated catalog from
`gen-fashion_firestore-data` without reseeding. No public API, schema, component,
or data-flow boundary changed.

Generate-phase authority hardening (2026-06-22, review #1 + #3): the production
generate run fixes the requester, explicit selection, and wearer age/gender on
the server, exposing only optional `style_description` to the model. The saved
trace/result reflect those effective values, and a selection missing any image
URL fails closed before the Runner starts. ADK is 41 passed, including the
constrained argument surface, injected-tool topology, trace/result
normalization, empty-style fallback, and missing-URL no-run cases. The smoke
script now checks authenticated `user_id` and exact ordered URL equality.

Live verification against `make dev` (2026-06-22): FastAPI 64 passed, ADK 41
passed, Flutter analyze clean / 12 passed, and diff checks are clean. Adult
session `9d09807b-f3c5-4479-a4f6-5bf2aa999747` and child session
`5a0a5fdd-a4e7-400e-aff4-7efb9a5ef601` both completed the real
propose→select→generate path with server-fixed authenticated user, gender/age,
and selected URLs in selection order; propose exposed no synthesis. Adult used
`gemini-2.5-flash-image`. Three child attempts used the existing collage
fallback, so this run could not add a new visual-child artifact; the persisted
tool result recorded `Outfit worn by a child female wearer`, proving the
application-side age/gender contract. A prior recovery run remains the visual
child-image evidence. No public API, Firestore, ES, or Flutter contract changed,
and no architecture-overview diagram update was required.


## Context and Orientation


**The two services.** `fastapi-service/` is the Python/FastAPI app the browser
talks to (auth, closet CRUD, session lifecycle, SSE). `adk-agent-service/` is the
Python ADK app (`styling_app/`) that runs the orchestrator + sub-agents and writes
the agent trace and result back to Firestore. They share Firestore
(`sessions/{id}` + its `agentEvents` subcollection, `users/{uid}/closet/{itemId}`,
`shared_closet/{itemId}`, `shared_closets/{closetId}`), Elasticsearch
(`clothing_items` index), and R2/MinIO object storage.

**The Flutter app** is `flutter-web-app/lib/`. The coordination flow lives in
`coordination/coordination_screen.dart`; the closet UI in `closet/`. The HTTP
client is `api/api_client.dart`.

**The current coordination flow (M5, working today).**

    Flutter  ── POST /sessions ──────────────▶ fastapi (sessions/{id} = SOURCE_SELECTING)
    Flutter  ── POST /sessions/{id}/source ──▶ fastapi  ─ HTTP ▶ adk /internal/run-session
                                                            (one background task:
                                                             SEARCHING → search_closet
                                                             → PROPOSING → GENERATING
                                                             → style_synthesizer
                                                             → COMPLETED + styleResult)
    Flutter  ── GET /sessions/{id}/stream ───▶ fastapi SSE  (polls agentEvents, relays)

Key files for this plan, with current behavior:

- `fastapi-service/app/domain/styling/value_objects.py` — `UserPreference`
  (occasion/season/style/color_preference; **no gender**), `CandidateItem`.
- `fastapi-service/app/domain/styling/aggregates.py` — `StyleSession` aggregate
  (`selected_items` exists; **no proposed_candidates**), with `select_source`,
  `propose`, `complete`, etc.
- `fastapi-service/app/domain/styling/state_machine.py` — transitions;
  `SEARCHING → PROPOSING → GENERATING → COMPLETED` are all already valid.
- `fastapi-service/app/handlers/session_routes.py` — `POST /sessions`,
  `POST /sessions/{id}/source`, `GET /sessions/{id}/stream`. `UserPreferenceRequest`
  has no gender. The SSE generator closes only on `COMPLETED`/`ERROR`/`TIMEOUT`.
- `fastapi-service/app/use_cases/styling/select_source.py` — builds the
  `AgentRunRequest` and calls `agent_run.start_session_run(...)`.
- `fastapi-service/app/ports/agent_run.py` — `AgentRunRequest`
  (session_id/user_id/source/user_preference/shared_closet_id).
- `fastapi-service/app/adapters/adk_agent_run.py` — posts to ADK
  `/internal/run-session`.
- `fastapi-service/app/adapters/firestore_styling_repo.py` — session<->document
  mapping (`_preference_to_document` etc.), `list_events`.
- `fastapi-service/app/handlers/closet_routes.py` — own-closet routes only.
- `fastapi-service/app/adapters/elasticsearch_embedding_repo.py` — M2-9 index
  mapping (`ensure_index`) + `index_item`.
- `fastapi-service/app/use_cases/closet/process_uploaded_item.py` — own-item
  analysis → `mark_ready` → ES `index_item`.
- `fastapi-service/app/adapters/firestore_closet_repo.py` — own-item
  document mapping (`_to_document` / `_from_snapshot`).
- `adk-agent-service/styling_app/server.py` — `RunSessionRequest`,
  `execute_run_session`, `_run_deterministic_fallback`. **The run loop.**
- `adk-agent-service/styling_app/adapters/firestore_session.py` —
  `update_status` (forward-only via `_STATUS_ORDER`), `write_event`,
  `write_style_result`, `mark_error`.
- `adk-agent-service/styling_app/agents/styling_agent.py` — `StylingAgent`
  (tools: `ask_preference`, `style_synthesizer`).
- `adk-agent-service/styling_app/tools/search_closet.py` — ES query via
  `adapters/elasticsearch.py` `hybrid_search`; no gender.
- `adk-agent-service/styling_app/tools/style_synthesizer.py` — Nano Banana
  generation; takes `style_description` only (no gender/age).
- `adk-agent-service/styling_app/tools/ask_preference.py` — normalizes
  preference fields; no gender.
- `adk-agent-service/styling_app/adapters/elasticsearch.py` — `hybrid_search`
  (filters user_id/closetId/category/colors; no gender).
- `adk-agent-service/styling_app/events.py` — `normalize_adk_event` (emits a
  tile per part: tool_call / tool_result / final_answer, plus a `thinking` tile
  for `transfer_to_agent`).
- `scripts/seed_shared_closet/run_seed.py` — `_label_meta`, `_build_closets`,
  `_ensure_es_index`, the per-item `es_doc` / `fs_doc`, closet metadata writes.
- `flutter-web-app/lib/coordination/coordination_screen.dart` — `_Controls`
  (form), `_TracePanel` + `AgentEventTile` (trace), `_ResultPanel`, `AgentEvent`.
- `flutter-web-app/lib/closet/closet_screen.dart`, `closet_item.dart` — own
  closet grid + model (no gender).
- `flutter-web-app/lib/api/api_client.dart` — `createSession`, `selectSource`,
  `streamSessionEvents`.

**Source of truth.** Requirements live in `docs/req-phase01.md` §18 (18.1
gender/age, 18.2 mandatory selection, 18.3 gallery + editable metadata, 18.4
trace curation / result split, 18.5 history) and ADL-026…ADL-029. The feature
matrix `docs/feature-matrix-phase01.md` rows ME-1…ME-7 track status.


## Plan of Work


The work is sequenced into six milestones ordered by dependency and to minimize
rework of the shared run loop. Each maps to feature-matrix rows:

- **Milestone A** → ME-2, ME-4 (gender foundation: domain field + seed data + ES
  mapping + own-item auto-gender). Pure data/plumbing; no flow behavior change.
- **Milestone B** → ME-6 (selection gate: two-phase run + `/select` + paused
  `PROPOSING` + Flutter candidate cards). The biggest structural change.
- **Milestone C** → ME-3 (thread gender + `closetKind` into search, styling
  prompt, and generation, built on B's two-phase run).
- **Milestone D** → ME-5 (curate the trace; separate candidate/result data from
  the thinking stream).
- **Milestone E** → ME-1 (shared-closet browse endpoints + Flutter gallery;
  own-item metadata edit endpoint + Flutter edit dialog).
- **Milestone F** → ME-7 (completion timestamp + owner-filtered history query +
  Flutter history gallery). This follow-up is independent of A–E.

Milestone B is placed before C deliberately: both restructure
`adk-agent-service/styling_app/server.py`, so establishing the two-phase shape
first means gender is threaded once, into the final structure, rather than into a
soon-to-be-rewritten single-phase loop.


### Milestone A — Gender dimension foundation (ME-2 + ME-4)


What will exist at the end that does not now: a `gender` field everywhere the
existing metadata fields live, an end-to-end-correct seed that writes
heuristic gender, and own-uploaded items that get an auto gender at analysis. No
change to the coordination flow's behavior yet (gender is carried but not yet
used to bias output — that is Milestone C).

Files and edits:

1. `fastapi-service/app/domain/styling/value_objects.py`: add
   `gender: Optional[str] = None` to `UserPreference`.

2. `fastapi-service/app/handlers/session_routes.py`: add `gender: str | None`
   to `UserPreferenceRequest` and pass it in `to_domain()`.

3. `fastapi-service/app/use_cases/styling/select_source.py`: include
   `"gender": preference.gender` in the `user_preference` dict sent to the agent.

4. `fastapi-service/app/adapters/firestore_styling_repo.py`: add `gender` to
   `_preference_to_document` and `_preference_from_document`.

5. Own-item gender (a small shared heuristic):
   - Add `_gender_for_category(category: Optional[str]) -> str` to
     `fastapi-service/app/use_cases/closet/process_uploaded_item.py` (female for
     `Dress`/`Skirt`/`Blouse`, else `common`).
   - Extend `ClothingItem.mark_ready(...)` in
     `fastapi-service/app/domain/closet/aggregates.py` with a `gender` argument
     and store it (`object.__setattr__(self, 'gender', gender)`); add the
     `gender: Optional[str] = None` field to the aggregate.
   - `process_uploaded_item.py`: compute `gender = _gender_for_category(analysis.category)`,
     pass to `mark_ready` and to `index_item`.
   - `fastapi-service/app/adapters/firestore_closet_repo.py`: add `gender` to
     `_to_document` and `_from_snapshot`.

6. ES mapping + indexing:
   - `fastapi-service/app/adapters/elasticsearch_embedding_repo.py`: add
     `"gender": {"type": "keyword"}` to the `ensure_index` mapping and a
     `gender: Optional[str]` parameter to `index_item` (write it into the doc).
   - `fastapi-service/app/ports/embedding_search.py`: add `gender` to the
     `index_item` abstract signature.

7. Seed (`scripts/seed_shared_closet/run_seed.py`):
   - Add `_label_gender(label: str) -> str` (same heuristic) and call it per item.
   - Add `"gender": {"type": "keyword"}` to `_ensure_es_index`.
   - Add `"gender": gender` to `es_doc` and `fs_doc`.
   - Re-run the seed locally with `--purge` then a fresh seed so existing 90
     items gain `gender` (idempotent; see Concrete Steps).

Acceptance: a reseed prints the usual summary and every `shared_closet` doc + ES
doc carries a `gender` of `female`/`common`; a freshly uploaded own item reaches
`READY` with a `gender` field in Firestore and ES; `UserPreference` round-trips
`gender` through the session document. fastapi pytest and adk pytest stay green.


### Milestone B — Mandatory candidate-selection gate (ME-6, must-fix)


What will exist: the coordination run pauses at `PROPOSING` with a set of
candidate items, the browser shows candidate cards, and image generation runs
only after the user picks items and confirms. This is the req §3 / §15 #6
compliance fix.

Design (two-phase run, per Decision Log):

- **Propose phase** (`phase="propose"`, triggered by `POST /sessions/{id}/source`):
  the ADK run searches the closet, writes the `search_closet` trace events,
  persists the candidate list to `sessions/{id}.proposedCandidates`, sets status
  `PROPOSING`, and **stops** — `style_synthesizer` is not invoked.
- The browser's SSE stream closes on `PROPOSING`-with-empty-`selectedItems`,
  emitting a `session.proposed` event carrying the candidates.
- **Select**: `POST /sessions/{id}/select { selectedItemIds: [...] }` validates a
  non-empty selection, persists `selectedItems`, and triggers the generate phase.
- **Generate phase** (`phase="generate"`): the ADK run calls `style_synthesizer`
  on the selected items, sets `GENERATING` → `COMPLETED` with `styleResult`.

Files and edits:

1. Domain: `fastapi-service/app/domain/styling/aggregates.py` — add
   `proposed_candidates: list[dict] = None` to `StyleSession` (default `[]` in
   `__post_init__`); add a `select_candidates(self, items: list[dict])` method
   that requires the current state to be `PROPOSING`, requires a non-empty list,
   and stores `selected_items` (no state transition here — the generate phase
   drives `PROPOSING → GENERATING`). The `PROPOSING → GENERATING` transition
   already exists in the state machine.

2. Repo mapping: `fastapi-service/app/adapters/firestore_styling_repo.py` — add
   `proposedCandidates` to `_to_document` / `_from_snapshot`.

3. Run request plumbing:
   - `fastapi-service/app/ports/agent_run.py` — add `phase: str = "propose"` and
     `selected_items: list[dict] | None = None` to `AgentRunRequest`.
   - `fastapi-service/app/adapters/adk_agent_run.py` — include `phase` and
     `selectedItems` in the JSON payload.
   - `select_source.py` — pass `phase="propose"` (explicitly) when starting the
     run.

4. New select route + use case:
   - `fastapi-service/app/use_cases/styling/select_candidates.py` — new
     `SelectCandidatesUseCase(styling_repo, agent_run)`: load the session
     (404 if missing / not owner), require state `PROPOSING`, resolve the
     requested `selectedItemIds` against `proposed_candidates` (reject unknown or
     empty → `ValueError`), call `session.select_candidates(resolved)`,
     `styling_repo.update(session)`, then `agent_run.start_session_run(
     AgentRunRequest(..., phase="generate", selected_items=resolved))` with the
     same `ERROR`-compensation pattern as `select_source`.
   - Export it from `fastapi-service/app/use_cases/styling/__init__.py`.
   - `fastapi-service/app/dependencies.py` — add
     `get_select_candidates_use_case()`.
   - `fastapi-service/app/handlers/session_routes.py` — add
     `POST /sessions/{session_id}/select` (body `{ selectedItemIds: [...] }`,
     202), mapping `StyleSessionNotFound` → 404, `ValueError` → 400/409,
     `AgentRunStartFailed` → 502 (mirror `select_source`).

5. SSE pause/resume: `fastapi-service/app/handlers/session_routes.py`
   `event_generator` — when the refreshed session is in `PROPOSING` **and** has
   no `selected_items`, drain remaining events then emit
   `_sse("session.proposed", { sessionId, status: "PROPOSING",
   candidates: refreshed.proposed_candidates })` and return. The terminal-state
   handling (`COMPLETED`/`ERROR`/`TIMEOUT`) is unchanged, so the re-opened stream
   after `/select` streams `GENERATING → COMPLETED` normally.

6. ADK two-run gate: `adk-agent-service/styling_app/server.py` plus agent factories
   - `RunSessionRequest` — add `phase: str = "propose"` and
     `selected_items: list[dict] | None = Field(default=None, alias="selectedItems")`.
   - Split `execute_run_session` on `request.phase`:
     - `propose`: build an orchestrator whose complete agent tree omits
       `style_synthesizer`, call `runner.run_async`, normalize every ADK event,
       collect candidates from its `search_closet` tool results, and persist them with a new
       `session_repo.write_proposed_candidates(session_id, candidates)` method
       (writes `proposedCandidates` + sets status `PROPOSING`), and return
       without generating. Only when the LLM returns no candidates, run the
       existing fixed top/bottom search fallback; it never generates.
     - `generate`: continue event seq numbering from the persisted max (new
       `session_repo.next_seq(session_id)`), build a generation-enabled
       `StylingAgent`, call `runner.run_async` with exactly the selected images,
       gender, and resolved wearer age, normalize its events, extract the style
       result, and write `COMPLETED`. Direct synthesis is allowed only when the
       consented agent run returns no result.
   - `agent.py`, `agents/orchestrator.py`, and `agents/styling_agent.py` provide
     phase-specific factories. The standalone ADK-discovery `root_agent` remains
     the full orchestrator; production obtains a fresh phase-specific agent.
   - `firestore_session.py` — add `write_proposed_candidates(session_id,
     candidates)` (merge `proposedCandidates` + `status: PROPOSING`, respecting
     `_STATUS_ORDER`) and `next_seq(session_id)` (max existing `agentEvents` seq
     + 1, or 1).

7. Flutter: `flutter-web-app/lib/api/api_client.dart` — add
   `selectCandidates({sessionId, selectedItemIds})` posting to
   `/sessions/{id}/select`. `coordination_screen.dart` — when the stream yields
   `session.proposed`, store the candidates and stop showing "running"; render a
   new `_CandidatePanel` of candidate cards (image + category + attribution;
   multi-select with the recommendation — the first/highest-ranked — pre-checked
   and badged), with a "Generate selected" `FilledButton` that is disabled until
   ≥1 item is checked; on press, call `selectCandidates(...)` then re-open the
   stream via the existing `_start`-style loop to watch `GENERATING → COMPLETED`.

Acceptance: with `SHARED_CLOSET` + `adult-01`, starting a run reaches
`PROPOSING`, the browser shows candidate cards, and **no** coordinate image is
generated until "Generate selected" is pressed; after pressing, generation runs
and the result image appears. The API smoke (adapted to the two-step flow) shows
the session sitting at `PROPOSING` with `proposedCandidates` and no `styleResult`
until `POST /sessions/{id}/select` is called.


### Milestone C — Gender propagation & child imagery (ME-3, must-fix)


What will exist: the chosen gender and the closet's adult/child kind reach
search, the styling prompt, and image generation, so `child-01` yields child
imagery and male/female/common bias results.

Files and edits:

1. Resolve `closetKind` for the run. In `adk-agent-service/styling_app/server.py`,
   derive `closet_kind` for `SHARED_CLOSET` runs from the selected
   `shared_closet_id` — read `shared_closets/{closetId}.kind` (a new
   `firestore_session.get_closet_kind(closet_id)` helper) or, as a fail-soft
   fallback, infer from the id prefix (`child-…` → `child`, else `adult`). For
   `CLOSET` runs, treat as `adult` (own-closet age is out of scope for Phase 1a).
   Carry `gender` (from `request.user_preference["gender"]`) and `closet_kind`
   through both phases.

2. Search filter/bias: `adk-agent-service/styling_app/tools/search_closet.py` —
   add an optional `gender` argument; pass it to
   `adapters/elasticsearch.py` `hybrid_search`, which adds a fail-soft `should`
   bias on the `gender` keyword (prefer matching gender or `common`; never hard-
   exclude, to avoid empty results on a small demo closet). Update the
   propose-phase search calls to pass `gender`.

3. Styling prompt + generation:
   - `adk-agent-service/styling_app/tools/style_synthesizer.py` — add `gender`
     and `wearer_age` (`"adult"`/`"child"`) parameters and weave them into the
     generation prompt/`style_description` (e.g. prepend "a {child|adult}
     {male|female|—} wearer"). **This is the concrete child-imagery fix.**
   - `adk-agent-service/styling_app/agents/styling_agent.py` — update
     `_INSTRUCTION` so the agent passes wearer gender/age to `style_synthesizer`.
   - `adk-agent-service/styling_app/tools/ask_preference.py` — add a `gender`
     parameter and echo it (kept consistent with `UserPreference`).
   - The generate phase in `server.py` passes `gender` + `wearer_age` into the
     `style_synthesizer` call.

Acceptance: a `child-01` run generates a **child** coordinate image (verified by
inspecting the generated image / the prompt sent to Nano Banana, and recorded in
Outcomes); switching gender between male/female/common visibly changes search
results and the generation prompt. (Local generation uses the Vertex SA path that
2026-06-21 verification confirmed produces real Nano Banana images; if quota
forces the collage fallback, verify the **prompt** carries child/gender and note
it.)


### Milestone D — Trace curation + result-UI separation (ME-5)


What will exist: the Accordion shows a concise, agent-turn-level thinking trace;
raw tool args/results and the `transfer_to_agent` plumbing no longer appear as
top-level dumps; candidate and result data live in the result UI (the candidate
panel from B and the result panel), per ADL-018's separate-stream rule.

Files and edits:

1. `adk-agent-service/styling_app/events.py` `normalize_adk_event` — stop
   emitting the `transfer_to_agent` `thinking` tile as a top-level event (it is
   plumbing, not user-facing thinking), and tag tool-result events that carry
   candidate/result payloads so the trace can summarize rather than dump them.
   Keep the full payload available (the result UI consumes `proposedCandidates` /
   `styleResult` from the session doc, not from the trace).

2. `flutter-web-app/lib/coordination/coordination_screen.dart` `AgentEventTile` —
   render a concise one-line summary per event (e.g. "ClosetAgent searched
   closet — 8 candidates") with the raw detail available only inside the
   expansion, and filter low-value kinds from the top-level list. The
   `search_closet` results and the final image are shown by `_CandidatePanel`
   (Milestone B) and `_ResultPanel`, not inline in the trace.

Acceptance: a run's Accordion contains only readable thinking-trace tiles (no raw
`args:{…}`/`result:{…}` dumps as the primary tile content, no `transfer_to_agent`
tile); candidate cards and the result image appear in their own panels.


### Milestone E — Closet gallery + editable metadata (ME-1)


What will exist: a browsable gallery of each shared closet's items with metadata,
and own-closet items whose searchable metadata (including gender) the user can
edit, with edits mirrored to ES.

Files and edits:

1. Shared-closet browse (read-only, backend-mediated):
   - `fastapi-service/app/adapters/shared_closet_search.py` (or a small new read
     method on it) — add `list_closets()` (read `shared_closets/*` metadata) and
     `list_items(closet_id)` (ES `closetId` term query → items with signed image
     URLs + metadata incl. `gender` + `attribution`).
   - New use cases `ListSharedClosetsUseCase` / `ListSharedClosetItemsUseCase`
     (or one use case with two methods) under `use_cases/styling/` or a new
     `use_cases/closet/` reader; wire in `dependencies.py`.
   - `fastapi-service/app/handlers/` — add `GET /shared-closets` and
     `GET /shared-closets/{closetId}/items` (auth required; read-only).
   - Flutter — add a gallery view (a new `closet/shared_closet_gallery.dart` and
     a tab/entry from the coordination or closet screen) that lists closets and,
     on selection, shows the item grid with metadata; reuse `Thumbnail` /
     `AttributionFooter`. Replace the bare `_sharedClosets` id dropdown's
     "browse" gap (the dropdown stays for selection; the gallery is the browse).

2. Own-item editable metadata (ADL-028):
   - `fastapi-service/app/use_cases/closet/update_item_metadata.py` — new
     `UpdateClosetItemMetadataUseCase(closet_repo, embedding_search)`: load the
     owner's item (404 if missing), apply provided fields
     (`gender`/`category`/`colors`/`season`/`tags`), `closet_repo.update(item)`,
     and re-`index_item` to ES (best-effort, mirroring the delete path's
     tolerance). Add a `set_metadata(...)` method to `ClothingItem` or reuse
     `mark_ready`-style setters.
   - `fastapi-service/app/handlers/closet_routes.py` — add
     `PATCH /closet/items/{item_id}` (auth; body of optional metadata fields).
   - `dependencies.py` — `get_update_item_metadata_use_case()`.
   - Flutter — `closet/closet_item.dart` gains a `gender` field;
     `closet_screen.dart` gains an item detail/edit dialog showing
     category/colors/season/tags/gender with the searchable fields editable,
     calling a new `api_client.dart` `updateItemMetadata(...)`.

Acceptance: each shared closet's items are browsable with metadata (category,
colors, season, tags, gender, attribution); editing an own item's gender via the
dialog persists and changes its ES document so a subsequent search reflects it.


### Milestone F — Completed-run history gallery (ME-7)


The ADK result writer stores `completedAt` with a Firestore server timestamp.
`StyleSession` and `FirestoreStylingRepository` map that field, and the styling
repository port exposes `list_completed(user_id, limit)`. `GET /sessions` is
authenticated, caps `limit` at 100, and returns completed runs newest first.
The required `userId` + `status` + descending `completedAt` composite index is
declared in `firestore.indexes.json`.

Flutter adds a typed history model, `ApiClient.listSessions`, a History
NavigationBar destination, and a gallery showing the generated coordinate,
completion date, source, and selected-item thumbnails. The screen covers loading,
failure, and empty states. It does not implement weather, duplication avoidance,
retry/rerun, or cursor pagination.

Acceptance: backend route tests prove owner/limit forwarding and populated/empty
responses; the adapter test proves the exact Firestore filter/order/limit chain;
the Flutter client test proves decoding/auth/limit, and the widget test proves
the generated image and formatted date render.


## Concrete Steps


All commands assume the repo root `/Users/ran/my-app/gen-fashion` unless noted.
Bring the local stack up first:

    make dev

Per-milestone verification commands (run from the named directory):

- fastapi unit tests:

      cd fastapi-service && python3 -m pytest -q

- adk unit tests:

      cd adk-agent-service && python3 -m pytest -q

- Flutter static + widget tests:

      cd flutter-web-app && flutter analyze && flutter test

- Re-seed the shared closet with gender (Milestone A), from
  `scripts/seed_shared_closet/`:

      python3 run_seed.py --purge
      curl -X DELETE "$ELASTICSEARCH_URL/clothing_items"
      python3 run_seed.py

  Expect a JSON summary with `created: 90` (after purge) and per-closet
  `{adult-01: 30, adult-02: 30, child-01: 30}`. Spot-check one ES doc and one
  `shared_closet` doc for a `gender` value.

- Closet smoke (own-item READY incl. gender, Milestone A/E):

      python3 scripts/m2_closet_smoke.py --expect-status READY

- Coordination smoke / browser E2E (Milestones B/C/D) — these will be adapted to
  the new two-step (propose → select → generate) flow; until the scripts are
  updated, drive the steps with the new endpoints and confirm the session sits at
  `PROPOSING` with `proposedCandidates` before `/select`, then reaches
  `COMPLETED` after:

      python3 scripts/m5_coordination_smoke.py --timeout-seconds 200
      python3 scripts/m5_coordination_browser_e2e.py --timeout-seconds 240

New tests to add alongside the code (narrowest meaningful checks):

- fastapi: `SelectCandidatesUseCase` (empty selection rejected; unknown id
  rejected; happy path persists `selectedItems` and triggers the generate run;
  failed trigger compensates to `ERROR`); `UserPreference` gender round-trip in
  the Firestore mapping; `UpdateClosetItemMetadataUseCase` mirrors ES;
  `session_routes` `/select` status-code mapping; SSE emits `session.proposed`
  at `PROPOSING`.
- adk: the propose agent tree recursively contains no `style_synthesizer`;
  `execute_run_session(phase="propose")` consumes normalized FakeRunner
  delegation/search events, stops at `PROPOSING`, and falls back only for zero
  candidates; `phase="generate"` resumes seq numbering, passes selected URLs +
  gender + child age to a StylingAgent, and writes `styleResult`.
- flutter: candidate panel renders cards and gates the Generate button on a
  selection; gender selector feeds the request; the trace tile shows a concise
  summary.


## Validation and Acceptance


Milestone-level acceptance is stated in each milestone above. The plan as a whole
is accepted when, against `make dev`:

1. (ME-3) Running a `SHARED_CLOSET` + `child-01` coordination produces a **child**
   coordinate image (or, if quota forces collage, a generation prompt that
   carries child + selected gender), and switching gender changes results.
2. (ME-6) Image generation never begins until the user selects candidates: the
   session pauses at `PROPOSING` with `proposedCandidates`, the browser shows
   candidate cards, and only "Generate selected" advances to `GENERATING` →
   `COMPLETED`.
3. (ME-1) Each shared closet is browsable with per-item metadata, and editing an
   own item's gender is reflected in a subsequent search.
4. (ME-5) The Accordion shows a curated thinking trace; candidates and result are
   in their own panels.
5. (ME-2/ME-4) Gender is present in `UserPreference`, the seed data, and ES.
6. (ME-7) The History destination lists only the authenticated user's completed
   sessions newest first, showing the generated image, completion date, and
   selected-item thumbnails; an account with no completed sessions sees the
   empty state.
7. Regression: `fastapi-service` pytest, `adk-agent-service` pytest, and
   `flutter analyze`/`flutter test` are all green; the M2 closet smoke reaches
   `READY`; the adapted coordination smoke + browser E2E reach `COMPLETED`.
8. Agent recovery: at least one live propose run contains native
   `transfer_to_agent`, model-authored `search_closet.description` values, no
   search fallback, and no `style_synthesizer`; the post-selection run contains
   the StylingAgent synthesizer call.

Record the concrete evidence (counts, session IDs, screenshots) in
`Outcomes & Retrospective` and mirror the status into
`docs/feature-matrix-phase01.md` (ME rows) as each milestone lands.


## Idempotence and Recovery


- The seed is idempotent (`item_id = uuid5(filename)`); `--purge` then reseed is
  the safe way to backfill `gender` onto the existing 90 items. ES `index`
  upserts; Firestore `set` overwrites — re-running is safe.
- ES mapping changes (`gender` keyword) only take effect on index **create**.
  Both `ensure_index` guards (`exists → return`) are no-ops on an existing index,
  so to pick up the new `gender` mapping locally, run `--purge`, explicitly
  `DELETE /clothing_items`, and then reseed. The seed recreates the index with
  the canonical mapping; re-run the closet smoke afterward for any own items.
- The two-phase run is resumable: the propose phase is safe to re-trigger (it
  rewrites `proposedCandidates` and stays at `PROPOSING`); the generate phase
  writes a fresh UUID-named coordinate object each call (no overwrite), so a
  retried `/select` cannot corrupt prior output. A failed trigger compensates the
  session to `ERROR` (same pattern as `select_source`).
- All new endpoints are additive; reverting a milestone is removing its routes /
  use cases / fields without touching the M5 flow, which keeps working with
  `selectedItems` defaulting to the recommendation if the gate is rolled back.


## Artifacts and Notes


- Heuristic gender mapping (shared between seed and own-item analysis):
  `female` ← {`Dress`, `Skirt`, `Blouse`}; otherwise `common`. `male` is a valid
  user/preference value but is not auto-assigned.
- New/changed HTTP surface introduced by this plan:
  - `POST /sessions/{id}/select` — confirm candidate selection, trigger generate.
  - `GET /shared-closets`, `GET /shared-closets/{closetId}/items` — browse.
  - `PATCH /closet/items/{id}` — edit own-item searchable metadata.
  - `session.proposed` SSE event — candidates at the `PROPOSING` pause.
- New session document fields: `proposedCandidates`, and the existing
  `selectedItems` becomes load-bearing for the generate gate.
- New persisted field across stores: `gender` (keyword in ES; field in
  `users/{uid}/closet/{itemId}`, `shared_closet/{itemId}`, and the session's
  `userPreference`).


## Interfaces and Dependencies


- **Elasticsearch `clothing_items` index** — gains a `gender` keyword; used for
  the gender bias and the shared-closet item listing.
- **Firestore** — `sessions/{id}` gains `proposedCandidates`; closet + shared
  closet docs gain `gender`; the shared-closet gallery reads `shared_closets/*` +
  `shared_closet/*` through the backend (client reads stay denied). ME-7 adds
  authoritative `completedAt` and a composite index over `userId`, `status`, and
  descending `completedAt`.
- **FastAPI `GET /sessions`** — authenticated first-page history list through
  `StylingRepositoryPort.list_completed`; `limit` defaults to 20 and caps at 100.
- **ADK `/internal/run-session`** — gains `phase` and `selectedItems`; still
  guarded by `X-Internal-Secret`.
- **Nano Banana (`gemini-2.5-flash-image`) via Vertex** — generation prompt gains
  wearer gender/age; behavior unchanged otherwise (collage fallback still
  applies).
- **No new third-party libraries.** All changes use the existing FastAPI, ADK,
  google-cloud-firestore, elasticsearch, boto3, and Flutter/Firebase stacks.


## Revision Notes


2026-06-21 — Initial authoring. Scope confirmed with the user as ME-1…ME-6
(ME-7 deferred). MD is paused for ME per the `ToDo` framing. `req-phase01.md` §18
+ ADL-026…029 are already in place (synced 2026-06-21) and are the source of
truth for this plan; the feature matrix ME rows and `docs/architecture-overview.md`
are updated in the same change that introduces this plan.

2026-06-24 — Reopened the previously deferred ME-7 at the user's request and
completed only its basic history slice. Added server-side completion timestamps,
the owner-filtered list query/API and composite index, Flutter history models/UI,
and focused tests. Synchronized the feature matrix and architecture overview;
future weather/deduplication/retry/pagination behavior remains excluded.

2026-06-21 — Completed milestones A–E. Updated the implementation sequence to
record the deterministic server-driven phase decision, corrected the local seed
recreation command discovered during verification, and recorded unit, seed,
API smoke, gallery/edit, child-prompt, release-build, and browser-E2E evidence.

2026-06-21 — Emergency recovery completed after review proved the deterministic
production driver had removed M4 agent behavior. Superseded that decision,
restored two phase-specific `runner.run_async` invocations with normalized real
events, kept generation absent from the propose agent tree, retained fixed code
only as phase-local fallback, and re-verified adult/child/browser flows.

2026-06-22 — Generate-phase authority hardening (review #1 + #3). Injected a
constrained `style_synthesizer` wrapper into the generate `StylingAgent` so the
LLM only sets `style_description`, while `user_id`, the ordered selected image
URLs, `gender`, and `wearer_age` are server-fixed. Normalized the recorded
tool-call trace and the saved `styleResult.items`/`selectedItems` to the
server-held selection, and made a selection missing any image URL fail before the
Runner starts. Added `build_agent_for_phase(..., style_tool=)` /
`build_styling_agent(..., style_tool=)`; the unchanged registry tool stays as the
generate fallback and as `root_agent`'s tool. Scope limited to reviews #1 and #3
(ES best-effort sync and the gender heuristic untouched). No public API,
Firestore, ES, or Flutter change, so the architecture-overview diagram is
unchanged. ADK suite 41 passed; smoke script asserts generate tool-call image
URLs equal the selected candidate URLs in order and the authenticated user ID.
Live verification completed against `make dev`: FastAPI 64 / ADK 41 / Flutter
analyze clean + 12 / diff checks clean; adult `9d09807b-…` and child
`5a0a5fdd-…` smokes both `COMPLETED` with the server-fixed values. Adult used the
real image model. Three child attempts used collage fallback; the persisted tool
result carried `child female wearer`, but no new visual child-image artifact was
claimed from this verification run.

2026-06-24 — Increased shared closets to 50 items each and added durable local
Firestore emulator snapshots via `gen-fashion_firestore-data`. `make dev` no
longer auto-seeds, `make clean` exports then stops without deleting data,
`make reset` is the explicit destructive path, and `make seed` now correctly
executes purge followed by seed. Live 150-item seed and container recreation
import passed. The architecture overview changed only to show the implemented
local persistence boundary; public APIs and production storage remain unchanged.
- Observation: `gcloud ... firestore start --export-on-exit` did not complete
  when Docker sent SIGTERM; the container reached the stop timeout and exited
  137 without writing an export. The emulator's explicit
  `/emulator/v1/projects/{project}:export` endpoint completed immediately and
  produced a valid `*.overall_export_metadata` file in the mounted volume.
  Implication: `make seed` and `make clean` explicitly snapshot the emulator;
  startup imports the latest metadata file. Container lifecycle no longer
  depends on signal forwarding inside the gcloud wrapper.

- Observation: the existing `make seed` target passed `--purge` and
  `--source-dir` in one invocation, but `run_seed.py` intentionally exits after
  purge. It therefore deleted shared data without recreating it. The target now
  runs purge and seed as separate commands and waits for ES, Firestore, and
  MinIO readiness first.

- Decision: Persist local Firestore emulator data through the named
  `gen-fashion_firestore-data` Docker volume, using explicit emulator export on
  `make seed`/`make clean` and automatic import at startup. Normal `make clean`
  preserves data; destructive removal is isolated as `make reset`. Rationale:
  shared closets are reference data and must not depend on reseeding every
  container launch. Date/Author: 2026-06-24 / User + Codex.

- Decision: Increase demo closets from 30 to 50 items each with separate adult
  and child category quotas. Adult closets retain more outerwear and
  dress/skirt variety; child favors tops and bottoms. The existing deterministic
  cursor keeps adult-01/adult-02 disjoint, and the live builder proved all 150
  image paths unique. Date/Author: 2026-06-24 / User + Codex.

2026-06-24 follow-up: local shared-closet durability is now verified, not merely
recovered by a seed rerun. The live stores contain 50/50/50 items. A Firestore
snapshot was written into `gen-fashion_firestore-data`; after the Firestore
container was stopped, deleted, and recreated, startup imported that snapshot
and REST reads returned the same 3 closets and 150 item docs without seeding.

2026-06-24 — Expanded the persisted catalog from 50 to 70 items per closet by
running the unchanged 50-item selection first and appending 10 tops plus 10
bottoms per closet. The incremental seed retained 150 records and created 60;
the updated Firestore snapshot restored all 210 records after container
recreation. Architecture topology is unchanged; only documented live counts
were synchronized.
