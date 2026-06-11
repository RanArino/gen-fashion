# M5 - Coordination Flow and Accordion UI


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


M5 turns the working closet data and working ADK agents into the first complete Web coordination experience. After this milestone, an authenticated Flutter Web user can start a styling session, choose `CLOSET` or `SHARED_CLOSET`, provide styling preferences, watch agent events arrive in a live Accordion UI, and receive a generated coordinate image stored through the existing R2/MinIO image path.

This plan covers the full M5 milestone from `docs/feature-matrix-phase01.md`: M5-1 through M5-11. It deliberately treats those requirements as one milestone because the session routes, `FirestoreStyleSessionRepository`, ADK run trigger, Firestore `agentEvents` relay, SSE endpoint, Flutter Accordion UI, and browser E2E test all share the same event and session contracts. Splitting them would leave engineers to infer the boundaries.

The visible acceptance target is a browser demo against local infrastructure: sign in with the Firebase Auth emulator, use a READY closet item or the seeded shared demo closet, start a session, select a source and preference, see live Accordion entries for `transfer_to_agent`, `search_closet`, and `style_synthesizer`, then see a final coordinate image URL and rendered result.


## Progress


- [x] (2026-06-11 15:24Z) Created the M5 ExecPlan and selected requirements M5-1 through M5-11 as one implementation milestone.
- [ ] Implement Phase 0 - contract alignment and tests for session state, Firestore document mapping, event normalization, and endpoint schemas.
- [ ] Implement Phase 1 - FastAPI session persistence, session routes, source selection validation, and ADK run trigger adapter.
- [ ] Implement Phase 2 - `adk-agent-service` internal run endpoint, ADK `Runner` execution, session state writes, and `agentEvents` relay.
- [ ] Implement Phase 3 - FastAPI SSE stream from Firestore `agentEvents`.
- [ ] Implement Phase 4 - Flutter coordination screen, source/preference controls, Accordion event UI, and final result UI.
- [ ] Implement Phase 5 - local E2E verification and feature matrix completion updates.


## Surprises & Discoveries


- Observation: The existing M5 files are stubs, not partial implementations.
  Evidence: `fastapi-service/app/handlers/session_routes.py` returns 501 for `POST /sessions`, `POST /sessions/{session_id}/source`, and `GET /sessions/{session_id}/stream`; `fastapi-service/app/adapters/firestore_styling_repo.py` and all `fastapi-service/app/use_cases/styling/*.py` raise `NotImplementedError`.
- Observation: The current Docker Compose value for `ADK_INTERNAL_BASE_URL` in `fastapi-service` points back to `http://fastapi-service:8000`.
  Evidence: `docker-compose.yml` sets `ADK_INTERNAL_BASE_URL=http://fastapi-service:8000`. M5 must change this to `http://adk-agent-service:3000` when adding the direct ADK trigger from ADL-020.
- Observation: `adk-agent-service` currently runs `adk api_server`, which exposes ADK development endpoints but not the M5 `POST /internal/run-session` endpoint.
  Evidence: `adk-agent-service/Dockerfile` and `docker-compose.yml` command both run `adk api_server --host 0.0.0.0 --port 3000`. M5 needs a small FastAPI wrapper for the internal run endpoint while keeping `adk web` usable for local agent debugging.


## Decision Log


- Decision: M5 reuses the existing M2 closet upload pipeline and does not add a second session-image upload path.
  Rationale: M2 already provides signed upload, processing, Firestore READY metadata, Elasticsearch indexing, signed download URLs, and browser E2E coverage. Duplicating that path under `/sessions` would increase storage and security surface without improving the M5 demo. The M5 "upload" acceptance means the user can upload or already have a READY closet item before starting coordination.
  Date/Author: 2026-06-12 / Codex

- Decision: The M5 Web flow starts agent execution from `POST /sessions/{session_id}/source`, not from a separate "run" button endpoint.
  Rationale: ADL-020 says Web execution starts after source selection. Combining source selection, preference capture, and run trigger keeps the API minimal: `POST /sessions` creates a session, then `POST /sessions/{id}/source` validates the source, stores `userPreference`, and asks `adk-agent-service` to run asynchronously.
  Date/Author: 2026-06-12 / Codex

- Decision: The `adk-agent-service` production/local HTTP entrypoint becomes a small FastAPI app with `POST /internal/run-session`, while `styling_app/agent.py` remains the ADK Web entrypoint.
  Rationale: `adk web` remains the right development UI for M4-style agent debugging, but M5 needs an application-specific HTTP endpoint that validates run requests, creates an ADK session, consumes `Runner.run_async()`, normalizes events, and writes Firestore. A wrapper avoids overloading FastAPI with ADK internals and keeps ADL-021 ownership in the ADK service.
  Date/Author: 2026-06-12 / Codex

- Decision: M5 implements a minimal A2UI-compatible result payload but does not block the milestone on `genui` if the Flutter Web spike is unstable.
  Rationale: ADL-018 says agent result UI should use A2UI and requires a Flutter Web spike. The minimal path is to store `a2uiPayload` events using a small standard subset for candidate cards and final result, then render with `genui` only if the spike passes. If it fails, the Flutter UI renders the same payload with local widgets for the MVP while preserving the transport contract.
  Date/Author: 2026-06-12 / Codex


## Outcomes & Retrospective


Not yet implemented. When the milestone completes, update this section with the browser E2E result, test counts, known limitations around Nano Banana quota or fallback usage, and any event-contract changes discovered while integrating ADK `Runner.run_async()`.


## Context and Orientation


The repository is `/Users/ran/my-app/gen-fashion`. `docs/req-phase01.md` is the requirements source of truth. `docs/feature-matrix-phase01.md` tracks implementation status. `docs/architecture-overview.md` visualizes the implemented-vs-planned boundary. M0 through M4 are complete locally. M5 is the next Phase 1a milestone and is the last blocker before M6 LINE work.

The system has two main services:

- `fastapi-service/` is the REST API used by Flutter Web. M2 closet routes are implemented here.
- `adk-agent-service/` is the Python ADK service implemented in M4. It exposes `styling_app/agent.py` for `adk web` and contains the working `StylingOrchestratorAgent`, `ClosetAgent`, `StylingAgent`, and tools.

M5 adds the bridge between those services:

- FastAPI owns authenticated session creation and source selection.
- FastAPI calls `adk-agent-service` directly over HTTP after source selection, per ADL-020.
- `adk-agent-service` owns execution progress, session state transitions during the run, and `sessions/{sessionId}/agentEvents` writes, per ADL-021.
- FastAPI streams `agentEvents` to Flutter via SSE, per ADL-011.
- Flutter renders the event stream as an Accordion UI and renders the final result.

Repository terms used in this plan:

- A style session is a Firestore document under `sessions/{sessionId}` that tracks one coordination run.
- `agentEvents` are Firestore subcollection documents under `sessions/{sessionId}/agentEvents/{eventId}`. They normalize ADK events into UI-friendly `tool_call`, `tool_result`, `thinking`, `final_answer`, and `a2ui_surface` records.
- `CLOSET` means the authenticated user's own READY closet items under `users/{uid}/closet`.
- `SHARED_CLOSET` means the M3-seeded demo data indexed as `user_id:"__shared__"` and carrying CC BY-SA 4.0 attribution.
- A2UI is the Agent-to-UI payload standard adopted by ADL-018 for user-facing result surfaces. Accordion thought trace events remain separate from A2UI result events.

Relevant existing files:

- `fastapi-service/app/handlers/session_routes.py` - M5 route stubs.
- `fastapi-service/app/adapters/firestore_styling_repo.py` - M5 Firestore adapter stub.
- `fastapi-service/app/ports/styling_repository.py` - current session persistence port.
- `fastapi-service/app/use_cases/styling/*.py` - M5 use case stubs.
- `fastapi-service/app/domain/styling/*` - current session aggregate, state machine, and value objects.
- `fastapi-service/app/dependencies.py` - existing dependency factories; M5 adds session and agent-run factories here.
- `adk-agent-service/styling_app/agent.py` - exports `root_agent` for ADK.
- `adk-agent-service/styling_app/tools/*` - working M4 tools.
- `flutter-web-app/lib/closet/*` - existing authenticated closet UI and API client patterns.


## Plan of Work


The implementation has six phases. Each phase has a focused acceptance check and leaves the repo coherent.

Phase 0 aligns contracts before wiring behavior. Update the session domain to match `docs/req-phase01.md` §8.1: statuses include `IMAGE_RECEIVED`, `ANALYZING`, `SOURCE_SELECTING`, `SEARCHING`, `PROPOSING`, `GENERATING`, `COMPLETED`, `ERROR`, and `TIMEOUT`; source supports `UNSET`, `CLOSET`, `SHARED_CLOSET`, and later `RAKUTEN`. Keep M6-only `RAKUTEN` out of the Web source picker unless the backend returns a clear 400. Add Pydantic route schemas for create, source selection, event stream serialization, and run trigger payloads. Add unit tests first for state transitions and mapping edge cases.

Phase 1 implements the FastAPI session side. Replace `FirestoreStylingRepository` stubs with real Async Firestore CRUD and event read helpers. Implement `CreateSessionUseCase` so `POST /sessions` creates a session with `SOURCE_SELECTING` and `source:"UNSET"`. Implement `SelectClothingSourceUseCase` so `POST /sessions/{id}/source` validates ownership, validates `CLOSET` has at least one READY item, allows `SHARED_CLOSET`, stores `userPreference` and optional `sharedClosetId`, then calls an `AgentRunPort` adapter. Add `AgentRunPort` and an HTTP adapter that POSTs to `ADK_INTERNAL_BASE_URL/internal/run-session` and expects `202 Accepted`.

Phase 2 implements the ADK run endpoint. Add a FastAPI wrapper under `adk-agent-service/styling_app/server.py` with `/health` and `POST /internal/run-session`. The endpoint should accept `{sessionId, userId, source, userPreference, sharedClosetId?}`; schedule a background task; immediately return `{accepted: true, sessionId}` with HTTP 202. The background task creates or reuses an ADK session with `InMemorySessionService`, calls `Runner.run_async()` with `root_agent`, passes session state through `state_delta`, normalizes each ADK event, writes `agentEvents`, and updates `sessions/{sessionId}` through an ADK-side Firestore session repository.

Phase 3 implements SSE. Add a FastAPI endpoint `GET /sessions/{session_id}/stream` that verifies the Firebase user owns the session, attaches a Firestore `on_snapshot` listener to `sessions/{sessionId}/agentEvents` ordered by `seq`, and yields Server-Sent Events. Include an initial session snapshot event, one event per new agent event, periodic keepalive comments, a terminal `session.completed` event, and error events when the session enters `ERROR`.

Phase 4 implements Flutter Web. Add a coordination screen reachable from the signed-in app shell. The screen should provide a compact source selector, shared closet selector for `adult-01`, `adult-02`, and `child-01`, a preference form, and a start action. After starting, subscribe to SSE and render Accordion rows grouped by `agentName` and `eventKind`. The final result area renders `styleResult.coordinateImageUrl`, selected items, attribution for `SHARED_CLOSET`, and an A2UI surface if present. Use local widgets if `genui` fails the spike, but keep the payload parsing isolated behind a small renderer boundary.

Phase 5 verifies locally. Run backend unit tests, ADK unit tests, Flutter tests, and a browser E2E path against `make dev` and `make web`. The E2E should use seeded `SHARED_CLOSET` first because it avoids needing a new upload. Then run a second smoke path with a READY user closet item if local M2 upload credentials and Gemini quota are available.


## Concrete Steps


Work from `/Users/ran/my-app/gen-fashion` unless a command says otherwise.

1. Inspect the current M5 stubs and confirm the baseline:

    rg -n "Implement in M5|NotImplementedError|SOURCE_SELECTING|agentEvents|ADK_INTERNAL_BASE_URL" fastapi-service adk-agent-service flutter-web-app docs
    git status --short

   Expected: only planned M5 stubs are found and the worktree contains only intentional edits.

2. Add backend contract tests before implementation:

    - Add or update `fastapi-service/tests/domain/test_style_session.py` to cover allowed transitions, `ERROR`, `GENERATING`, and terminal states.
    - Add `fastapi-service/tests/adapters/test_firestore_styling_repo_mapping.py` with mocked Firestore snapshots for session and `agentEvents` mapping.
    - Add `fastapi-service/tests/use_cases/test_styling_use_cases.py` covering create session, source validation, `CLOSET` empty rejection, `SHARED_CLOSET` acceptance, and ADK trigger call.
    - Add `fastapi-service/tests/test_session_routes.py` covering auth-required 401, create 200, source invalid 400, source accepted 202 or 200, and stream auth/ownership checks.

   Run:

    cd fastapi-service
    pytest tests/domain/test_style_session.py tests/use_cases/test_styling_use_cases.py tests/test_session_routes.py -q

   Expected before implementation: new tests fail on M5 stubs. Expected after Phase 1 and Phase 3: tests pass.

3. Update FastAPI domain and ports:

    - In `fastapi-service/app/domain/styling/state_machine.py`, align states with req §8.1 and ADL-009. Include `ERROR` and `GENERATING`.
    - In `fastapi-service/app/domain/styling/value_objects.py`, add `UNSET` or a separate nullable source mapping, plus fields needed by the documented `CandidateItem`: `name`, `price`, `category`, `external_url`, and optional `attribution`. Keep compatibility with existing M4 tool dicts.
    - In `fastapi-service/app/domain/styling/aggregates.py`, add `analysis_result`, `selected_items`, `style_result`, and timeout/error helpers as needed. Keep methods shallow and explicit.
    - In `fastapi-service/app/ports/styling_repository.py`, add methods for event writing and event streaming only if they are used by FastAPI. Do not put ADK-only behavior in FastAPI unless both services share the port.
    - Add `fastapi-service/app/ports/agent_run.py` defining `AgentRunPort.start_session_run(...)`.

   Verify:

    cd fastapi-service
    pytest tests/domain/test_style_session.py -q

4. Implement `FirestoreStylingRepository` in FastAPI:

    - Use `google.cloud.firestore.AsyncClient` with `project=settings.project_id` and `database=settings.firestore_database_id`, matching `FirestoreClosetRepository`.
    - Store sessions at top-level `sessions/{sessionId}` using the exact fields from req §8.1.
    - Map timestamps with the same `_parse_datetime` style used by `FirestoreClosetRepository`.
    - Implement ownership-safe `get_by_id(user_id, session_id)` by loading the document and returning `None` when `userId` does not match.
    - Add an event query helper for `sessions/{sessionId}/agentEvents` ordered by `seq` if SSE needs one-off backfill before attaching `on_snapshot`.

   Verify:

    cd fastapi-service
    pytest tests/adapters/test_firestore_styling_repo_mapping.py -q

5. Implement FastAPI use cases and dependency factories:

    - `CreateSessionUseCase.execute(user_id)` returns `{session_id, status}` or a typed DTO, not just a string.
    - `SelectClothingSourceUseCase.execute(...)` loads the session, rejects non-owned sessions, validates source, stores preference, and starts the ADK run through `AgentRunPort`.
    - Keep `AnalyzeClothingImageUseCase`, `SearchCandidateItemsUseCase`, and `GenerateCoordinateUseCase` as compatibility/orchestration use cases that delegate to the M4 tools through the ADK run, unless a direct route needs them. They should no longer raise `NotImplementedError`.
    - Add dependency factories in `fastapi-service/app/dependencies.py` for session use cases and `AgentRunPort`.
    - Add `ADK_INTERNAL_BASE_URL` config default as `http://localhost:3000` for host local development, and set Compose to `http://adk-agent-service:3000`.

   Verify:

    cd fastapi-service
    pytest tests/use_cases/test_styling_use_cases.py -q

6. Implement FastAPI session routes:

    - `POST /sessions` uses `verify_firebase_token` and returns HTTP 200 or 201 with `{session_id, status:"SOURCE_SELECTING"}`.
    - `POST /sessions/{session_id}/source` accepts JSON `{source, userPreference, sharedClosetId?}`. It returns HTTP 202 with `{session_id, status:"SEARCHING"}` after ADK run trigger acceptance.
    - Return 400 for invalid sources, 404 for non-owned sessions, 409 for invalid state transitions, and 422 for malformed request bodies.
    - Keep `RAKUTEN` rejected with 400 in Phase 1a because M6 owns Rakuten.

   Verify:

    cd fastapi-service
    pytest tests/test_session_routes.py -q

7. Add the ADK-side Firestore and event writer:

    - Add `google-cloud-firestore==2.13.1` or a compatible pinned version to `adk-agent-service/requirements.txt`.
    - Add Firestore settings to `adk-agent-service/styling_app/config.py`: `firestore_database_id`, `firestore_emulator_host` if needed, and the same `project_id` behavior as FastAPI.
    - Add `adk-agent-service/styling_app/adapters/firestore_session.py` with methods to update session status, write `styleResult`, write `agentEvents`, and mark errors.
    - Add `adk-agent-service/styling_app/events.py` to normalize ADK events. Preserve `author`, function call name/args, function response, final text, and `thought_signature` as base64 when present. Use `seq` as a monotonic per-session integer and set `ttlAt` to `createdAt + 24h`.

   Verify:

    cd adk-agent-service
    pytest styling_app/tests -q

   Add focused tests such as `styling_app/tests/test_event_normalizer.py` and `styling_app/tests/test_firestore_session.py` with mocked clients.

8. Add `POST /internal/run-session` to `adk-agent-service`:

    - Add `adk-agent-service/styling_app/server.py`.
    - Create a FastAPI `app` with `/health` and `POST /internal/run-session`.
    - Use `BackgroundTasks` or `asyncio.create_task` so the HTTP response is immediate. For local reliability, record an initial `agentEvents` row before returning 202 or update session status to `SEARCHING`.
    - Use `Runner(agent=root_agent, app_name="styling_app", session_service=InMemorySessionService())`.
    - Before calling `run_async`, call `create_session(app_name="styling_app", user_id=user_id, session_id=session_id, state={...})`.
    - Pass a `new_message` that describes the run in natural language and a `state_delta` containing `sessionId`, `userId`, `source`, `sharedClosetId`, and `userPreference`.
    - While iterating events from `runner.run_async(...)`, write each normalized event to Firestore and update session statuses: `SEARCHING` when search starts, `PROPOSING` when candidates are available, `GENERATING` when `style_synthesizer` is called, `COMPLETED` when final result is written, `ERROR` on exceptions.
    - Extract the final `styleResult` from `style_synthesizer` function response when possible. If extraction is ambiguous, write a final-answer event and mark the session `COMPLETED` only when a coordinate URL is present.

   Verify with a local mocked run test:

    cd adk-agent-service
    pytest styling_app/tests/test_run_session_endpoint.py -q

   Then verify service boot:

    cd adk-agent-service
    uvicorn styling_app.server:app --host 0.0.0.0 --port 3000
    curl -f http://localhost:3000/health

9. Update Docker and local environment wiring:

    - Change `docker-compose.yml` `fastapi-service` `ADK_INTERNAL_BASE_URL` to `http://adk-agent-service:3000`.
    - Add `FIRESTORE_EMULATOR_HOST=firestore-emulator:8080` and `FIRESTORE_DATABASE_ID=(default)` to `adk-agent-service` in Compose.
    - Change `adk-agent-service` Compose command to `python -m uvicorn styling_app.server:app --host 0.0.0.0 --port 3000 --reload`.
    - Change `adk-agent-service/Dockerfile` CMD to the same uvicorn app for container runs. Keep `adk web` documented as a manual development command.
    - Update `.env.example` files for `ADK_INTERNAL_BASE_URL` and ADK Firestore settings.

   Verify:

    docker-compose build fastapi-service adk-agent-service
    docker-compose up fastapi-service adk-agent-service firestore-emulator elasticsearch minio
    curl -f http://localhost:3000/health
    curl -f http://localhost:8000/health

10. Implement SSE in FastAPI:

    - Add `sse-starlette` only if a standard streaming response is insufficient. Prefer FastAPI `StreamingResponse` first to avoid a dependency.
    - Use Firestore `on_snapshot` from the sync client if AsyncClient lacks listener support; isolate that bridge in a small adapter so tests can fake it.
    - Format events as SSE:
      - `event: session.snapshot`
      - `event: agent.event`
      - `event: session.completed`
      - `event: session.error`
    - Each `data:` payload should be JSON with stable keys and include `sessionId`.
    - Include keepalive comments every 15 seconds while the session is non-terminal.
    - Close the stream after `COMPLETED`, `ERROR`, or `TIMEOUT`.

   Verify:

    cd fastapi-service
    pytest tests/test_session_routes.py -q

   Manual local verification after starting Compose:

    curl -N -H "Authorization: Bearer <emulator-id-token>" http://localhost:8000/sessions/<session_id>/stream

   Expected: initial snapshot arrives, then agent events arrive in `seq` order, then the stream closes on completion.

11. Implement Flutter API client and coordination screen:

    - Extend `flutter-web-app/lib/closet/api_client.dart` or add `flutter-web-app/lib/coordination/session_api_client.dart` for `createSession`, `selectSource`, and `streamSessionEvents`.
    - Add source selection controls using segmented controls or radio-style buttons. Do not expose `RAKUTEN` in Phase 1a.
    - Add preference controls for occasion, style, season, and color preference.
    - Add `EventSource` or a package-backed SSE client that works on Flutter Web. Keep it wrapped so tests can inject fake event streams.
    - Add Accordion widgets under `flutter-web-app/lib/coordination/` with stable row heights and clear collapsed/expanded states. Show agent name, event kind, tool name, short text, and expandable JSON detail for tool calls/results.
    - Add final result widgets that display the coordinate image URL, selected item thumbnails, and CC BY-SA attribution when any item source is `SHARED_CLOSET`.
    - Wire the coordination screen into the authenticated app shell without disrupting the existing closet upload/list/delete flow.

   Verify:

    cd flutter-web-app
    flutter analyze
    flutter test

12. Add local E2E smoke coverage:

    - Prefer adding a small script under `scripts/` or a Playwright test if the repo already has browser E2E helpers. Keep it minimal and deterministic.
    - The first E2E uses `SHARED_CLOSET` because M3 seeded data removes the need for an upload.
    - Steps: start `make dev`, sign in with the Auth emulator through `make web`, create session, select `SHARED_CLOSET` and a demo closet, submit preference, assert Accordion receives at least one `tool_call` and one `tool_result`, assert final coordinate image URL is shown.
    - Optional second E2E: upload one item through existing M2 flow, wait for READY, then select `CLOSET` and assert ownership filtering.

   Verify:

    make dev
    make web
    <run chosen E2E command>

   Expected: the browser completes a full coordination session and displays a generated coordinate image or the M4 collage fallback image.

13. Final verification and documentation sync:

    - Run all relevant checks:

        cd fastapi-service && pytest -q
        cd adk-agent-service && pytest -q
        cd flutter-web-app && flutter analyze && flutter test
        cd firebase && npm test

    - Run `make dev` smoke if local Docker and credentials are available.
    - Update `docs/feature-matrix-phase01.md`: mark M5 rows `✅ Implemented` only after the browser E2E passes. Until then keep them `🟡 In progress`.
    - Update `docs/architecture-overview.md` when code changes move M5 nodes from Stub to WIP or Done.
    - Update this ExecPlan's `Progress`, `Surprises & Discoveries`, and `Outcomes & Retrospective`.


## Validation and Acceptance


Backend acceptance:

- `cd fastapi-service && pytest -q` passes, including session route, use case, repository, and SSE tests.
- `POST /sessions` with a valid Firebase emulator token returns a new session owned by that user with `status:"SOURCE_SELECTING"` and `source:"UNSET"`.
- `POST /sessions/{id}/source` rejects `CLOSET` when the user has zero READY closet items, accepts `SHARED_CLOSET`, writes preference data, and calls the ADK run endpoint.
- Non-owners cannot read or stream another user's session.

ADK acceptance:

- `cd adk-agent-service && pytest -q` passes, including event normalization and run endpoint tests.
- `POST /internal/run-session` returns 202 immediately and writes Firestore session/event updates asynchronously.
- A live run against M3 `SHARED_CLOSET` produces `tool_call`, `tool_result`, and terminal result events. The event stream preserves `author` for orchestrator/sub-agent visibility.
- When Nano Banana quota is unavailable locally, the M4 collage fallback still stores a reachable image and the session reaches `COMPLETED`.

SSE acceptance:

- `GET /sessions/{id}/stream` returns `text/event-stream`.
- The stream emits an initial session snapshot, ordered agent events, keepalive comments during long runs, and a terminal completion or error event.
- The stream closes after terminal state and does not leak events across users.

Flutter acceptance:

- `cd flutter-web-app && flutter analyze && flutter test` passes.
- In Chrome, the signed-in user can create a session, select `SHARED_CLOSET`, submit preferences, and see live Accordion rows without layout overlap on desktop and mobile widths.
- The final result shows the coordinate image and attribution for shared closet items.

End-to-end acceptance:

- With local `make dev` and seeded shared closet data, the full browser path works: sign in, start session, select shared closet, run agents, watch Accordion updates, and see final coordinate image or collage fallback.
- The feature matrix is updated from `🟡 In progress` to `✅ Implemented` only after the above E2E passes.


## Idempotence and Recovery


The document and test additions are safe to re-run and revise. Firestore session writes should be idempotent by document ID: `POST /sessions` intentionally creates a new UUID every call, while `POST /sessions/{id}/source` should reject terminal sessions and should not start duplicate ADK runs for a session already in `SEARCHING`, `PROPOSING`, `GENERATING`, or `COMPLETED`.

ADK event writes should use deterministic document IDs derived from `seq`, such as zero-padded sequence numbers, or use Firestore auto IDs with a unique `seq` field and duplicate detection. Prefer deterministic `eventId = f"{seq:06d}"` for local recovery. If the run task crashes, the session should enter `ERROR` with an error event; the user can create a new session rather than retrying the same one.

SSE connections are repeatable. On reconnect, the endpoint should send a current session snapshot and then backfill existing events ordered by `seq` before listening for new events. This lets browser refreshes recover without starting a second agent run.

Docker Compose changes are reversible. If `adk-agent-service` fails to boot under the new FastAPI wrapper, run `cd adk-agent-service && adk web` manually to verify the M4 agent app still loads, then debug `styling_app/server.py` separately.

No destructive data migration is required. Firestore TTL for `agentEvents.ttlAt` must be enabled before public deployment, but local emulator tests can assert the field exists without relying on TTL deletion.


## Artifacts and Notes


Selected requirements:

- M5-1 `CreateSessionUseCase`
- M5-2 `FirestoreStyleSessionRepository`
- M5-3 `SelectClothingSourceUseCase`
- M5-4 `AnalyzeClothingImageUseCase`
- M5-5 `SearchCandidateItemsUseCase`
- M5-6 `GenerateCoordinateUseCase`
- M5-7 Session lifecycle and timeout
- M5-8 ADK to Firestore event relay
- M5-9 SSE streaming endpoint
- M5-10 Flutter Accordion UI
- M5-11 Web coordination flow E2E

Expected Firestore session shape:

    sessions/{sessionId}
      userId: string
      status: "IMAGE_RECEIVED" | "ANALYZING" | "SOURCE_SELECTING" | "SEARCHING" | "PROPOSING" | "GENERATING" | "COMPLETED" | "ERROR" | "TIMEOUT"
      source: "UNSET" | "CLOSET" | "SHARED_CLOSET" | "RAKUTEN"
      sharedClosetId: string | null
      analysisResult: map | null
      userPreference: map | null
      selectedItems: array
      styleResult: map | null
      createdAt: timestamp
      updatedAt: timestamp
      expiresAt: timestamp | null

Expected Firestore event shape:

    sessions/{sessionId}/agentEvents/{eventId}
      seq: int
      agentName: string
      eventKind: "thinking" | "tool_call" | "tool_result" | "final_answer" | "a2ui_surface"
      toolName: string | null
      toolArgs: map | null
      toolResult: map | null
      text: string | null
      a2uiPayload: map | null
      thoughtSignature: string | null
      createdAt: timestamp
      ttlAt: timestamp

Internal ADK run request:

    POST /internal/run-session
    {
      "sessionId": "uuid",
      "userId": "firebase-uid",
      "source": "SHARED_CLOSET",
      "sharedClosetId": "adult-01",
      "userPreference": {
        "occasion": "casual weekend",
        "season": "spring",
        "style": "clean casual",
        "colorPreference": "blue and white"
      }
    }

SSE payload example:

    event: agent.event
    data: {"sessionId":"...","seq":3,"agentName":"ClosetAgent","eventKind":"tool_call","toolName":"search_closet","toolArgs":{"source":"SHARED_CLOSET","description":"white shirt"}}

Architecture overview sync note: creating this plan changes the feature matrix status to `🟡 In progress`, but the code-state diagrams in `docs/architecture-overview.md` should remain Stub-colored until implementation replaces the current 501 and `NotImplementedError` stubs.


## Interfaces and Dependencies


FastAPI interfaces:

- `POST /sessions` - authenticated; creates a session.
- `POST /sessions/{session_id}/source` - authenticated; validates source/preference and starts ADK run.
- `GET /sessions/{session_id}/stream` - authenticated; streams SSE events.
- `AgentRunPort` - new FastAPI output port for direct HTTP call to ADK.

ADK interfaces:

- `POST /internal/run-session` - internal; starts an asynchronous ADK run and writes Firestore.
- `GET /health` - internal/local health check for Compose.
- `styling_app/agent.py` - remains the `adk web` entrypoint for manual M4/M5 debugging.

Libraries and services:

- `google-adk==2.1.0` - already used by M4; M5 uses `Runner.run_async()`.
- `google-cloud-firestore` - already in FastAPI; must be added to ADK service for ADL-021.
- Firebase Auth emulator - used for authenticated Web and route tests.
- Firestore emulator - stores sessions and `agentEvents` locally.
- Elasticsearch - searched by M4 `search_closet`.
- MinIO/R2 - stores source clothing images and generated coordinate images.
- Gemini / Vertex AI - used by M4 tools; local demo may use collage fallback when image generation quota is unavailable.
- Flutter Web - renders the coordination UI and Accordion stream.
- Optional `genui` package - spike for A2UI rendering; keep isolated behind a renderer boundary.
