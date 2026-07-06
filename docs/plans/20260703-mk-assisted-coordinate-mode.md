# MK - Assisted Coordinate Mode


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


The current Coordinate flow asks the user for style preferences, searches either the user's closet or one shared demo closet, pauses at `PROPOSING`, lets the user check candidate cards, and generates one coordinate image from the selected image URLs. This plan adds a second Web Coordinate mode, called **Assisted Coordinate**, for the shopping-aided workflow in the user requirements.

After this change, a signed-in user can upload or choose up to three of their own clothes as anchor items, select the same style preferences used by the current Coordinate screen, and ask the agent to propose a complete styling that can include both clothes and accessories such as a white T-shirt, black hat, bag, shoes, or belt. Suggested purchasable items come from Rakuten Ichiba Item Search / Affiliate data and render as selectable candidate cards with images, names, prices, and outbound links. Anchors stay selected by default, while the agent's recommended purchasable suggestions are default-checked at most once per outfit category so a single coordinate does not start with duplicate bottoms, shoes, or other same-slot alternatives; the user may uncheck, swap, save interesting suggestions to their closet, change preferences and rerun proposal, or proceed directly to generation. The generated image uses the actual selected image URLs, reusing the current post-selection `style_synthesizer` path.

The closet also gains a clear ownership classification: user-uploaded or bought items are **Owned**, while agent-suggested saved items start as **Interesting**. Both Owned and Interesting READY items remain selectable/searchable in the user's closet, while the existing processing state (`PROCESSING` / `READY` / `ERROR`) continues to describe image-analysis readiness only.

Observable success: in Flutter Web, the Coordinate tab has an Assisted mode. A user uploads one to three anchor items, sees Rakuten-backed suggestions with default check marks, saves one suggestion as Interesting, changes it to Owned in the closet UI, selects both Owned and Interesting items in the Coordinate flow, and generates a coordinate image. Backend, ADK, Flutter, and Firestore rules tests pass.


## Progress


- [x] (2026-07-03) ExecPlan authored after reading the current Coordinate, closet, session, ADK, Firestore, ES, Flutter, feature matrix, and architecture docs.
- [x] (2026-07-03) `docs/req-phase02.md`, `docs/feature-matrix-phase02.md`, and `docs/architecture-overview.md` synchronized for planned MK work.
- [x] (2026-07-03) MK-1 - Assisted Coordinate mode contract and session fields are implemented and tested (`CoordinationMode`, `anchor_items`, `select_assisted`, Firestore mapping, `POST /sessions/{id}/assist`, ADK `mode`/`anchorItems`).
- [x] (2026-07-03) MK-2 - Up-to-three own-clothes anchor selection/upload is implemented in Flutter and enforced in FastAPI (`AssistSessionUseCase` 1..3/owner/READY checks; Flutter mode toggle + `_AnchorPicker` with max-3 enforcement, upload via existing `UploadService`).
- [x] (2026-07-03) MK-3 - Rakuten Ichiba item search adapter/tool is implemented with affiliate-aware output and tests (`adapters/rakuten.py`, `tools/search_rakuten.py`, config/env placeholders).
- [x] (2026-07-03) MK-4 - Agent proposal output supports text styling suggestions plus purchasable item images (assisted ClosetAgent instruction + `search_rakuten` tool, anchor merge, deterministic Rakuten fallback, unavailable degradation).
- [x] (2026-07-03) MK-5 - User selection, default recommendation checks, preference edits, and generation reuse the existing two-phase gate (recommended/anchor candidates checked by default in `CandidatePanel`; preference rerun starts a fresh session via Start; generation still goes through `POST /sessions/{id}/select`).
- [x] (2026-07-03) MK-6 - Save-suggestion-to-closet and ownership status transitions are implemented (`POST /closet/import-suggestion`, `ownershipStatus` in `PATCH /closet/items/{id}`, Rakuten card "Add to closet" button, closet edit dialog ownership dropdown, `OwnershipChip`).
- [x] (2026-07-03) MK-7 - Existing Coordinate-from-closet includes Interesting items (READY-only filtering everywhere; ownership never filters search/anchors; covered by `test_select_source_closet_accepts_interesting_ready_item`).
- [x] (2026-07-03) MK-8 - End-to-end validation passes locally: fastapi pytest 106 passed, adk pytest 56 passed, `flutter analyze` clean + 24 tests passed, Firestore rules 7 passed (dockerized emulator), `m5_coordination_smoke.py` COMPLETED, new `mk_assisted_coordinate_smoke.py` COMPLETED on the Rakuten-degraded path. Live-Rakuten output pending valid credentials (configured keys return 403).
- [x] (2026-07-03, post-review feedback) Rakuten 403 root-caused and fixed: the 20260701 endpoint requires `Origin`/`Referer` headers matching the registered application URL (`RAKUTEN_APPLICATION_URL`); adapter now sends them and upsizes `_ex=128x128` thumbnails to 400x400. `mk_assisted_coordinate_smoke.py --require-rakuten` COMPLETED with 10 live Rakuten candidates and a real suggestion import. Also from user feedback: mode labels renamed to self-explanatory names with per-mode hint text (Closet Styling / Style & Shop; クローゼットコーデ / 買い足し提案), and freshly uploaded anchors now appear as analyzing/loading tiles while PROCESSING instead of being hidden until READY. adk pytest 57 passed; flutter analyze clean + 25 tests passed.
- [x] (2026-07-04, post-launch UX follow-up) MK-6's per-candidate "Add to closet" button required a separate tap before generation and was easy to miss, so users' Rakuten selections weren't reliably ending up in the closet. Added a post-generation confirmation modal (`_SaveInterestingDialog` in `coordination_screen.dart`): once a coordinate image is generated, any selected-but-not-yet-saved Rakuten candidates are offered in a dialog, all pre-checked, letting the user uncheck any before confirming; confirmed items are saved as `INTERESTING` via the existing `_importSuggestion`/`POST /closet/import-suggestion` path (no backend changes). The manual per-candidate button remains for saving before generation without including an item in the current outfit. `flutter analyze` clean; `flutter test` 28 passed (3 new widget tests added: modal appears with Rakuten items pre-checked, unchecking skips import, closet-only generation never shows the modal).
- [x] (2026-07-04, bug fix) User reported History cards showing hanger-icon placeholders instead of real thumbnails for Rakuten items in a completed session's selected-items row, suspecting the new save-Interesting modal had a timing bug. Root cause was unrelated to import timing: `HistoryScreen`'s selected-item thumbnails used `Image.network` without the `webHtmlElementStrategy` CORS workaround already applied to `CandidateCard`/`_SaveInterestingDialog` (see the 2026-07-03 "post-live" Surprise below), so Rakuten CDN images always fell through to the broken-image placeholder there. Fixed by threading `source` through the stack: `SelectedItemResponse.source` (`session_routes.py`, sourced from the already-present `source` key on `session.selected_items` candidate dicts) -> `HistorySelectedItem.source` (`history_item.dart`) -> `history_screen.dart` now sets `webHtmlElementStrategy: WebHtmlElementStrategy.prefer` for `source == 'RAKUTEN'` thumbnails, `.never` otherwise. fastapi pytest 106 passed (1 new assertion); flutter analyze clean; flutter test 29 passed (1 new test asserting the per-source strategy).
- [x] (2026-07-04, post-launch UX follow-up) With Owned and Interesting items now mixed in one closet grid (Milestone F), a user with more than a handful of items had no way to narrow the view — everything rendered as one flat `GridView`. Added a `ClosetFilterBar` above `ClosetGrid` in `closet_screen.dart`: a `SegmentedButton<ItemOwnership?>` for All/Owned/Interesting (reusing the mode-selector pattern from `coordination_screen.dart`), plus `FilterChip`s for `category`, derived dynamically from the distinct non-blank `category` strings present in the ownership-filtered items (no new enum — `category` stays free text). Filtering is client-side via a new pure `applyClosetFilters()` function; `ClosetGrid` itself is unchanged and still only ever receives an already-filtered list, so it stays a pure renderer usable by widget tests. A new `_NoFilterMatchState` covers the zero-results case distinctly from the existing "add your first item" `_EmptyState`. New l10n keys `filterAll`/`noItemsMatchFilter` added to both arb files. New tests: `test/closet_filter_bar_test.dart` (5 widget tests) and `test/closet_filters_test.dart` (6 pure-function tests). `flutter analyze` clean; `flutter test` 41 passed (up from 29).
- [x] (2026-07-04, layout fix, same follow-up) First render of `ClosetFilterBar` used `SectionCard` (a `Card`) inside a default-alignment `Column`, so it shrink-wrapped to its content width and rendered as a centered floating card, visually disconnected from both the app bar above and the grid below it - not the integrated toolbar look intended. Fixed by giving the wrapping `Column` in `_buildBody` `crossAxisAlignment: CrossAxisAlignment.stretch` and replacing `SectionCard` with a flat, full-width `Container` (`AppColors.panel` background, `AppColors.border` bottom border, no card elevation/margin) whose `Wrap` content is left-aligned and sits flush under the app bar. Removed the now-unused `theme/components.dart` import. `flutter analyze` clean; same 16 closet-suite tests (`closet_filter_bar_test.dart`, `closet_filters_test.dart`, `closet_grid_test.dart`) still pass, confirming the visual fix didn't change filter behavior.
- [x] (2026-07-05, post-launch UX fix) User reported that when they selected a top and inner item, the agent correctly suggested bottoms/shoes but the UI auto-selected three pants even though the app generates only one coordinate at a time. Fixed both sides: Assisted prompts now explicitly tell the agent to balance one coordinate across missing outfit slots and avoid multiple auto-recommended items for the same category, and `_applyDefaultSelection()` now keeps all anchors selected but accepts only the first recommended candidate per inferred outfit slot (`bottom`, `shoes`, `outer`, `accessory`, `top`). The proposal grid still shows all alternatives for manual swapping. Added a widget regression test with one top anchor, three recommended bottoms, and one recommended shoe; only the anchor, first bottom, and shoe are checked by default. `flutter test test/coordination_screen_test.dart` passed; `flutter analyze` clean; ADK targeted tests (`test_agents.py`, `test_run_session_endpoint.py`) passed.
- [x] (2026-07-06, post-launch UX fix) User reported that Rakuten image options had dropped too far: the recommendation/default-check should be one purchasable item, but the UI still needs several EC options for the user to choose from. Fixed the ADK server-bound `search_rakuten` tool to fetch at least five display candidates even if the LLM asks for `limit: 1`, and changed Assisted candidate finalization so only the first Rakuten suggestion is marked `recommended` while the remaining Rakuten candidates stay visible and unchecked. Added ADK regression tests for both behaviors.


## Surprises & Discoveries


- Observation: `ClothingSource.RAKUTEN` already exists in `fastapi-service/app/domain/styling/value_objects.py`, but both implemented execution paths reject it.
  Evidence: `fastapi-service/app/use_cases/styling/select_source.py` raises `ValueError("RAKUTEN is not available in Phase 1a")`, and `adk-agent-service/styling_app/tools/search_closet.py` accepts only `CLOSET` and `SHARED_CLOSET`.

- Observation: the current Coordinate flow already has the right safety gate for this feature: propose first, pause in `PROPOSING`, then generate only after `POST /sessions/{id}/select`.
  Evidence: `fastapi-service/app/use_cases/styling/select_candidates.py` validates selected candidate ids against `session.proposed_candidates` and starts the generate-phase ADK run with server-held `selected_items`.

- Observation: closet readiness and closet ownership are currently conflated if we try to reuse `status`.
  Evidence: `fastapi-service/app/domain/closet/value_objects.py` defines only `PROCESSING`, `READY`, and `ERROR`; `SelectClothingSourceUseCase` includes only `READY` closet items for `CLOSET` source. An "Interesting" item can still be generation-ready, so it needs a separate ownership field.

- Observation: ADK image generation can already fetch public external HTTP(S) image URLs, which de-risks generating from Rakuten candidates before they are saved to R2.
  Evidence: `adk-agent-service/styling_app/adapters/image_storage.py::fetch_bytes` fetches non-R2 `http://` / `https://` URLs with `httpx.get(..., follow_redirects=True)`.

- Observation: the Rakuten Ichiba Item Search API has a newer 2026-07-01 endpoint and requires an application id plus access key; affiliate id is optional but needed for affiliate links.
  Evidence: official Rakuten Web Service docs at `https://webservice.rakuten.co.jp/documentation/ichiba-item-search` list endpoint `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701` and shared `applicationId` / `accessKey` inputs.

- Observation (2026-07-03, implementation): an exception raised inside an ADK tool aborts the whole agent run (`google.adk...functions.py` re-raises `tool_error`), so a raised `RakutenUnavailableError` marked the assisted session `ERROR` during the live smoke. Fixed by having the server-bound `search_rakuten` tool catch `RakutenUnavailableError` and return `[]`, letting the anchor/closet degradation path take over.
  Evidence: first `mk_assisted_coordinate_smoke.py` run ended in `session.error`; adk-agent-service logs show the tool traceback; after the catch-and-degrade fix the smoke reaches `COMPLETED`.

- Observation (2026-07-03): `RAKUTEN_APPLICATION_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID` are configured in the repo `.env`, but the 20260701 endpoint returns 403 for both query-parameter and `accessKey`-header auth, so the keys are invalid/expired/not yet activated rather than the request format being wrong (docs confirm both auth styles). Live-Rakuten suggestion output is therefore unverified; the degradation path is verified live instead.
  Evidence: `curl` probes with the configured keys return 403 in both styles; docs state accessKey "can be provided in either header or as query parameter".
  RESOLVED (2026-07-03, later same day): the keys were valid all along. The 403 body is `REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING`: the migrated `openapi.rakuten.co.jp` endpoint validates `Origin`/`Referer` headers even for server-to-server calls (undocumented in the official reference; confirmed by community migration notes). The adapter now sends `Origin`/`Referer` from `RAKUTEN_APPLICATION_URL` and live search returns real items; `--require-rakuten` smoke passes with 10 Rakuten candidates.

- Observation (2026-07-03, post-live): with live Rakuten candidates the cards rendered but every thumbnail failed with Flutter Web `HTTP request failed, statusCode: 0`. The image URL was correct (`mediumImageUrls[0]`, the primary product image); the failure was CORS: Rakuten's `thumbnail.image.rakuten.co.jp` CDN serves `200 image/jpeg` with **no `Access-Control-Allow-Origin` header**, and the CanvasKit renderer fetches image bytes cross-origin (which needs CORS). Fixed by rendering Rakuten candidate images with `Image.network(..., webHtmlElementStrategy: WebHtmlElementStrategy.prefer)`, which displays them via an HTML `<img>` element that does not require CORS. Closet/anchor images keep the default byte path.
  Evidence: `curl -D -` on the thumbnail URL shows 200 image/jpeg with no `access-control-allow-origin`; `statusCode: 0` is the CanvasKit cross-origin image-fetch failure signature.

- Observation (2026-07-03): `firebase emulators:exec` needs a host Java runtime, which this machine lacks; the rules tests were run instead against the dockerized `firestore-emulator` (`npm test` connects to `127.0.0.1:8080`). Caveat: `initializeTestEnvironment` loads `firestore.rules` into that shared emulator and they persist, which then 403s the smoke scripts' unauthenticated emulator REST reads — restart the emulator container after rules tests before running smokes.
  Evidence: `java -version` fails; rules 7/7 pass via the container; `m5_coordination_smoke.py` failed with `PERMISSION_DENIED` until `docker-compose restart firestore-emulator`.

- Observation (2026-07-04): widget-testing `coordination_screen.dart`'s full `Start -> propose -> Generate selected` flow inside the default 800x600 test surface fails silently — `tester.tap()` on the "Start"/"Generate selected" `FilledButton`s warns the offset is outside the render view and the tap never reaches `onPressed`, with no test failure until a later assertion finds an empty widget tree. Fixed by calling `tester.binding.setSurfaceSize(const Size(900, 2600))` (reset via `addTearDown`) before pumping. Separately, once `_maybeOfferSaveInteresting()`'s `showDialog` is on screen, `tester.pumpAndSettle()` times out (`pumpAndSettle timed out`) even though the dialog itself is static; a bounded loop of `tester.pump(const Duration(milliseconds: 100))` (10x) works instead. Both fixes are in `coordination_screen_test.dart`'s three new save-Interesting tests and should be reused by future tests that drive this screen's full session flow.
  Evidence: tap warnings referenced `Offset(...) outside the bounds of the root of the render tree, Size(800.0, 600.0)`; `_start`/`streamSessionEvents` debug prints confirmed `onPressed` never fired until the surface was enlarged; `pumpAndSettle` only stopped timing out after switching to bounded `pump()` calls post-dialog.


## Decision Log


- Decision: Add `ownershipStatus` (or backend snake_case `ownership_status`) instead of adding `INTERESTING` to `ClothingItemStatus`.
  Rationale: `ClothingItemStatus` is an analysis pipeline state used to decide whether an image is searchable/generatable. A Rakuten-saved Interesting item should be `READY` and searchable immediately, while still visually classified as Interesting. Separate fields keep the pipeline logic shallow and avoid breaking existing `READY` filters.
  Date/Author: 2026-07-03 / ExecPlan

- Decision: Store user-uploaded items as `OWNED` by default and Rakuten-saved suggestions as `INTERESTING` by default; allow only `INTERESTING` <-> `OWNED` transitions for this plan.
  Rationale: The requirement's "already-purchased" and "already-bought" are the same user concept for the product UI. Two states are enough for the requested glanceable classification and avoid a premature shopping lifecycle model.
  Date/Author: 2026-07-03 / ExecPlan

- Decision: Implement Assisted Coordinate as a session `mode` (`STANDARD` default, `ASSISTED` new) rather than treating it as a third closet source.
  Rationale: Assisted mode can mix owned closet anchors and Rakuten suggestions in one proposal, so `source` alone is too narrow. Keeping `source` on each candidate item (`CLOSET`, `SHARED_CLOSET`, `RAKUTEN`) preserves current history/result semantics and avoids overloading `ClothingSource`.
  Date/Author: 2026-07-03 / ExecPlan

- Decision: Add a dedicated `search_rakuten` ADK tool instead of extending `search_closet` to accept `RAKUTEN`.
  Rationale: closet search and Rakuten search have different credentials, rate-limit behavior, fields, attribution, and failure modes. A separate tool keeps `search_closet` stable for current Coordinate and makes trace previews clearer.
  Date/Author: 2026-07-03 / ExecPlan

- Decision: Save Rakuten suggestions to R2/MinIO when adding them to the closet, even though generation can use their external image URLs directly.
  Rationale: the closet is owner-private and already renders through signed download URLs. Importing the suggestion image to `{uid}/closet/{uuid}.jpg` gives stable thumbnails, delete behavior, and ES indexing parity with uploaded items.
  Date/Author: 2026-07-03 / ExecPlan

- Decision: Enforce the "maximum of 3 clothes" as the Assisted-mode anchor limit, not as a new global closet cap.
  Rationale: the existing closet cap is 20 and should remain unchanged. The new limit applies to the clothes the user uploads/selects for one assisted run.
  Date/Author: 2026-07-03 / ExecPlan


## Outcomes & Retrospective


All milestones (A-G / MK-1…MK-8) landed on 2026-07-03. Code is uncommitted per instruction.

What shipped, by milestone:

- **A (ownership model):** `ClosetOwnershipStatus` (`OWNED`/`INTERESTING`) + `origin`/external metadata on `ClothingItem`; Firestore mapping defaults missing `ownershipStatus` to `OWNED`; ES mapping/index/update accept the new keyword fields fail-soft; `PATCH /closet/items/{id}` accepts `ownershipStatus`.
- **B (import):** `ImportSuggestedClosetItemUseCase` + `POST /closet/import-suggestion`; only candidates proposed into the caller's own session import; image copied to `{uid}/closet/{uuid}.jpg` via new `ImageStoragePort.put_image_bytes`; item lands READY + INTERESTING + indexed.
- **C (Rakuten):** `adk-agent-service/styling_app/adapters/rakuten.py` (20260701 endpoint, formatVersion 1/2 tolerant, affiliate pass-through, typed `RakutenUnavailableError`) + `tools/search_rakuten.py` (CandidateItem-shaped output, `rakuten:{itemCode}` ids, `Rakuten Ichiba` attribution); config + `.env.example`/docker-compose placeholders; assisted-only wiring into `ClosetAgent`.
- **D (assisted session):** `CoordinationMode`/`anchor_items`/`select_assisted` on `StyleSession` + Firestore mapping; `AssistSessionUseCase` validating 1..3 owner READY anchors and the daily limit before the ADK launch; `POST /sessions/{id}/assist`; ADK `mode`/`anchorItems` on `RunSessionRequest`, assisted propose message, anchor merge with `recommended` defaults, deterministic Rakuten fallback, unavailable → anchor-only degradation. Assisted prompts now tell the agent to balance one coordinate across missing outfit slots and avoid multiple auto-recommended items for the same category.
- **E/F (Flutter):** Standard/Assisted segmented mode, `_AnchorPicker` (injectable stream for tests, max 3, upload), `ApiClient.assistSession`/`importSuggestedItem`, mixed `CandidatePanel`/`CandidateCard` (source chip, name/price/outbound link, Add-to-closet → Saved-as-Interesting state, default checks from `anchor` plus at most one `recommended` candidate per inferred outfit slot), `OwnershipChip` + ownership dropdown in the closet edit dialog, en/ja l10n.
- **G (validation):** new `scripts/mk_assisted_coordinate_smoke.py` (anchor upload → 0-anchor 400 → assisted propose → recommended anchor → import-or-degrade → INTERESTING→OWNED → generate COMPLETED → Standard CLOSET reuse → history), plus the full suites.

Final verification (2026-07-03, local `make dev` stack):

    fastapi-service:  pytest -q            -> 106 passed, 1 skipped
    adk-agent-service: pytest -q           -> 56 passed
    flutter-web-app:  flutter analyze      -> No issues found
                      flutter test         -> 24 passed (All tests passed!)
    firebase rules:   npm test (dockerized firestore emulator) -> 7 pass, 0 fail
    scripts/m5_coordination_smoke.py --timeout-seconds 180     -> COMPLETED (no regression)
    scripts/mk_assisted_coordinate_smoke.py --timeout-seconds 240 -> COMPLETED
      (anchor recommended; ownership INTERESTING->OWNED persisted; Standard
       CLOSET reuse proposed; history has the coordinate image; Rakuten
       degraded path exercised because the configured keys return 403)

Post-review feedback fixes (2026-07-03, later same day):

    adk-agent-service: pytest -q           -> 57 passed (adapter header + thumbnail tests)
    flutter-web-app:  flutter analyze      -> No issues found
                      flutter test         -> 25 passed (processing-anchor tile test added)
    scripts/mk_assisted_coordinate_smoke.py --require-rakuten -> COMPLETED
      (11 candidates, 10 live Rakuten; real suggestion imported as INTERESTING
       then flipped to OWNED; generation and Standard reuse verified)

Post-launch UX follow-up (2026-07-04, save-Interesting confirmation modal):

    flutter-web-app:  flutter analyze      -> No issues found
                      flutter test         -> 28 passed (3 new tests for the
                      post-generation save-Interesting modal)

Post-launch UX follow-up (2026-07-04, closet ownership/category filter bar):

    flutter-web-app:  flutter analyze      -> No issues found
                      flutter test         -> 41 passed (11 new tests: 5 for
                      ClosetFilterBar widget behavior, 6 for the pure
                      applyClosetFilters function)

Deviations from the plan:

- The server-bound assisted `search_rakuten` tool catches `RakutenUnavailableError` and returns `[]` instead of letting it propagate — a raised tool error aborts the whole ADK run (discovered live; see Surprises).
- Live-Rakuten candidates could not be validated at first: the configured `RAKUTEN_*` keys return 403 for both documented auth styles. RESOLVED later the same day — the endpoint requires `Origin`/`Referer` headers (see Surprises); with the adapter fix, `--require-rakuten` passes with live candidates.
- Firestore rules tests ran against the dockerized emulator (`npm test` directly) because the host has no Java for `firebase emulators:exec`; restart the emulator container afterwards before running smokes (loaded rules persist and 403 the smoke's emulator REST reads).
- `CandidatePanel`/`CandidateCard` were made public (previously private `_`-classes) so widget tests can drive them directly, matching the existing `AgentEventTile` precedent.
- No `fastapi-service` Rakuten config was needed (search lives in the ADK service; import consumes session-held candidate URLs), so `app/config.py` was left untouched.


## Context and Orientation


Repository layout relevant to this plan:

- `flutter-web-app/lib/home/home_screen.dart` hosts the four current tabs: Closet, Coordinate, History, Shared. It still switches tabs with `_index`; MG routing is separate and not required for MK.
- `flutter-web-app/lib/coordination/coordination_screen.dart` implements the current Coordinate UI. It has source selection (`SHARED_CLOSET` / `CLOSET`), style preference fields, a trace panel, `_CandidatePanel` with checkboxes, `_ResultPanel`, and calls `ApiClient.createSession`, `selectSource`, `streamSessionEvents`, and `selectCandidates`.
- `flutter-web-app/lib/closet/closet_screen.dart` implements own-closet upload/list/delete/edit. It listens directly to `users/{uid}/closet`, renders `StatusBadge` for analysis status, and edits category/colors/season/tags/gender through `PATCH /closet/items/{id}`.
- `fastapi-service/app/domain/closet/*` has `ClothingItem` and `ClothingItemStatus`. Only analysis states exist today.
- `fastapi-service/app/domain/styling/*` has `StyleSession`, `UserPreference`, `CandidateItem`, and `ClothingSource`; `RAKUTEN` exists in the enum but is blocked.
- `fastapi-service/app/handlers/session_routes.py` exposes `POST /sessions`, `POST /sessions/{id}/source`, `POST /sessions/{id}/select`, `GET /sessions/{id}/stream`, and history reads.
- `fastapi-service/app/use_cases/styling/select_source.py` validates source and starts the ADK propose phase. It rejects `RAKUTEN`.
- `fastapi-service/app/use_cases/styling/select_candidates.py` persists explicit selection and starts the ADK generate phase.
- `adk-agent-service/styling_app/server.py` executes two phases: `propose` collects candidates from tool results and writes `proposedCandidates`; `generate` calls `style_synthesizer` only with selected image URLs fixed by the server.
- `adk-agent-service/styling_app/tools/search_closet.py` searches ES-backed own/shared closets. It does not search external products.
- `adk-agent-service/styling_app/tools/style_synthesizer.py` fetches the selected image URLs and writes the generated coordinate image under `{uid}/coordinates/{uuid}.jpg`.

Terms used in this plan:

- **Standard Coordinate**: the existing Coordinate flow in `coordination_screen.dart`.
- **Assisted Coordinate**: the new mode from this plan. It starts from one to three user-owned anchor clothes and can suggest external Rakuten items/accessories.
- **Anchor item**: one of the user's own `READY` closet items selected for the assisted run. The UI may upload new anchors through the existing closet upload pipeline, but the backend contract receives closet item ids after they are `READY`.
- **Suggested item**: a candidate proposed by the agent, usually from Rakuten. Suggested items have text fields plus an image URL and can be checked for generation.
- **Interesting**: a saved suggestion that the user wants to remember, but has not marked as owned.
- **Owned**: a user-uploaded or purchased/bought item. This is the status users should interpret as "already bought".

Assumptions:

- Assisted Coordinate requires at least one and at most three `READY` anchor items for one run. The existing global closet cap remains `MAX_CLOSET_IMAGES_PER_USER=20`.
- Rakuten credentials are backend/agent secrets only. The browser never receives `applicationId`, `accessKey`, or affiliate secrets.
- If Rakuten API credentials are absent locally, adapter tests use fakes and the UI surfaces a clear unavailable state; the rest of Standard Coordinate remains unaffected.


## Plan of Work


### Milestone A - Data contracts and closet ownership

Add the smallest data model needed to classify closet items without disturbing current processing state.

In `fastapi-service/app/domain/closet/value_objects.py`, add `OwnershipStatus` or `ClosetOwnershipStatus` with values `OWNED` and `INTERESTING`. Keep `ClothingItemStatus` unchanged. In `fastapi-service/app/domain/closet/aggregates.py`, add fields:

- `ownership_status: ClosetOwnershipStatus = OWNED`
- `origin: str | None` with expected values `USER_UPLOAD`, `RAKUTEN`
- optional external metadata for imported suggestions: `external_item_id`, `external_url`, `affiliate_url`, `price`, `brand_or_shop`

Update `FirestoreClosetRepository` mapping so existing documents default to `OWNED` when `ownershipStatus` is absent. Update `ElasticsearchEmbeddingRepository.ensure_index`, `index_item`, and `update_item_metadata` so `ownershipStatus`, `origin`, `externalItemId`, and `externalUrl` can be indexed as keyword fields. Use fail-soft ES updates like the existing metadata path.

Extend `PATCH /closet/items/{item_id}` or add `PATCH /closet/items/{item_id}/ownership` to allow the owner to switch `INTERESTING` <-> `OWNED`. The simplest path is extending the existing metadata patch body with `ownershipStatus`, because it already enforces owner scope and mirrors to ES.

Verification for Milestone A:

    cd fastapi-service
    python -m pytest tests/domain/test_clothing_item.py tests/adapters/test_firestore_closet_repo_mapping.py tests/use_cases/test_closet_use_cases.py -q

Acceptance: existing closet documents read as Owned by default; an Interesting item can be persisted, read back, updated to Owned, and remains `READY`.


### Milestone B - Import Rakuten suggestions into the user's closet

Add a backend use case that turns a proposed Rakuten candidate into a private closet item.

Create `ImportSuggestedClosetItemUseCase` in `fastapi-service/app/use_cases/closet/import_suggested_item.py`. It receives the authenticated `user_id`, the current `session_id`, and a proposed candidate id. It loads the session, verifies ownership, finds the candidate in `session.proposed_candidates`, requires `source == "RAKUTEN"`, checks the closet cap, downloads the candidate image URL, stores it under `{uid}/closet/{new_uuid}.jpg`, creates a `ClothingItem` with `status=READY`, `ownershipStatus=INTERESTING`, `origin=RAKUTEN`, and metadata copied from the candidate, and indexes it in ES.

Extend `ImageStoragePort` and `R2ImageStorage` with a write-bytes method such as `put_image_bytes(image_path, data, content_type="image/jpeg")`. Keep existing upload URL behavior unchanged.

Add `POST /closet/import-suggestion` in `fastapi-service/app/handlers/closet_routes.py` with body `{sessionId, candidateId}`. Return `{item_id, status, ownershipStatus}`. Do not allow arbitrary external URLs in the request; only import candidates already proposed into the caller's session.

Verification for Milestone B:

    cd fastapi-service
    python -m pytest tests/test_closet_routes.py tests/use_cases/test_closet_use_cases.py -q

Acceptance: importing a Rakuten candidate creates one new private READY closet document with `ownershipStatus=INTERESTING`, stores the image in R2/MinIO, indexes it for future closet search, and rejects candidates not present in the caller's session.


### Milestone C - Rakuten adapter and ADK tool

Implement external item search as a separate tool.

Add config to `adk-agent-service/styling_app/config.py` and `fastapi-service/app/config.py` as needed:

- `rakuten_application_id`
- `rakuten_access_key`
- `rakuten_affiliate_id`
- `rakuten_search_endpoint`, defaulting to the official 2026-07-01 Ichiba Item Search endpoint
- `rakuten_request_timeout_seconds`
- `rakuten_max_results`

Add `.env.example` and `docker-compose.yml` placeholders for local development. Do not add real secrets.

Create `adk-agent-service/styling_app/adapters/rakuten.py` and `adk-agent-service/styling_app/tools/search_rakuten.py`. The tool accepts a concrete query, optional category hint, colors, min/max price if added later, and limit. It returns CandidateItem-shaped dicts:

- `item_id`: stable prefixed id such as `rakuten:{itemCode}`
- `source`: `RAKUTEN`
- `name`
- `image_url`
- `price`
- `category`
- `tags`
- `external_url`
- `affiliate_url`
- `shop_name`
- `attribution`: `Rakuten Ichiba`

Use the official API's `keyword` search first. Keep genre/attribute search out of scope unless keyword search proves insufficient. If `rakuten_affiliate_id` is present and the API returns affiliate URL fields, pass them through; otherwise use the item URL. On missing credentials, raise a typed unavailable exception so the propose fallback can still return closet-only suggestions if possible.

Register the tool in `styling_app/tools/registry.py` and update `adk-agent-service/styling_app/agents/closet_agent.py` so Assisted mode can use both `search_closet` and `search_rakuten`.

Verification for Milestone C:

    cd adk-agent-service
    python -m pytest styling_app/tests/test_tools.py styling_app/tests/test_registry.py styling_app/tests/test_agents.py -q

Acceptance: with a mocked Rakuten response, `search_rakuten` maps item name, image URL, price, item URL/affiliate URL, and source correctly; `search_closet` behavior for `CLOSET` and `SHARED_CLOSET` is unchanged.


### Milestone D - Assisted session contract and agent execution

Extend sessions with Assisted mode while keeping Standard Coordinate compatible.

Add optional fields to `StyleSession` and Firestore mapping:

- `coordination_mode`: `STANDARD` by default, `ASSISTED` for this flow
- `anchor_items`: list of user's own selected closet items

Add a new FastAPI route in `session_routes.py`, preferably `POST /sessions/{session_id}/assist`, with body:

- `anchorItemIds`: list of 1 to 3 own closet item ids
- `userPreference`: same shape as the current `UserPreferenceRequest`

The use case validates:

- session belongs to the user and is `SOURCE_SELECTING`
- `anchorItemIds.length` is 1..3
- every anchor is owned by the caller and `status == READY`
- daily generation limit is checked in the same locations as current source/select

The use case stores `coordinationMode=ASSISTED`, `source=CLOSET`, `anchorItems`, and user preference, then starts the ADK propose phase with `mode="assisted"` and `anchorItems`.

In `adk-agent-service/styling_app/server.py`, extend `RunSessionRequest` with `mode` and `anchorItems`, defaulting to Standard behavior. For assisted propose, instruct the agent to treat anchor items as fixed context and search Rakuten for complementary clothes/accessories. The proposal should include:

- anchor closet items as selected/recommended candidates
- Rakuten suggestions with concrete text labels and image data
- a small number of recommendations, with default UI checks balanced to at most one item per outfit category

The existing generate phase can be reused if `selectedItems` contain image URLs. Keep the server-side binding of selected image URLs; the model must not supply arbitrary URLs.

Update fallback logic so Assisted mode does not call only `search_closet` for top/bottom; it should produce at least one deterministic Rakuten query from `style`, `occasion`, `season`, and colors, then use closet anchors plus any external results.

Verification for Milestone D:

    cd fastapi-service
    python -m pytest tests/domain/test_style_session.py tests/adapters/test_firestore_styling_repo_mapping.py tests/use_cases/test_styling_use_cases.py tests/test_session_routes.py -q

    cd adk-agent-service
    python -m pytest styling_app/tests/test_run_session_endpoint.py styling_app/tests/test_event_normalizer.py -q

Acceptance: Standard `POST /sessions/{id}/source` still works unchanged; Assisted `POST /sessions/{id}/assist` rejects 0 or 4 anchors, rejects non-owner/missing/non-READY anchors, writes Assisted mode fields, and reaches `PROPOSING` with mixed anchor/Rakuten candidates under mocked tools.


### Milestone E - Flutter Assisted Coordinate UI

Refactor `flutter-web-app/lib/coordination/coordination_screen.dart` enough to add mode-specific controls without duplicating the whole screen.

Add a mode segmented control at the top of the Coordinate controls:

- Standard: current behavior, source selector remains `SHARED_CLOSET` / `CLOSET`
- Assisted: show anchor picker/upload flow and hide the current shared closet selector

For Assisted mode, build:

- a compact anchor selector that reads the user's `READY` closet items from Firestore and allows max 3 selected
- an upload action reusing `UploadService`; uploaded anchors appear once they become `READY`
- the same style/occasion/season/color/gender/language controls as Standard
- a Start button that calls `ApiClient.assistSession` instead of `selectSource`

Extend `ApiClient` with `assistSession`, `importSuggestedItem`, and ownership-status update support. Keep current `selectSource` and `selectCandidates` tests green.

Update `_CandidatePanel` / `_CandidateCard` for mixed candidates:

- selected by default when it is an anchor, or when candidate has `recommended == true` and no already selected candidate occupies the same outfit category
- show source chip: Own closet / Rakuten
- show name, price, and external link for Rakuten suggestions
- show "Add to closet" for Rakuten candidates, which calls import and updates the card to indicate it was saved as Interesting
- let users uncheck/check recommendations before generation

Support preference changes by allowing the user to edit the preference fields and rerun Assisted proposal before generation. This can be implemented as starting a new session for the rerun rather than mutating a `PROPOSING` session, which keeps the state machine simple.

Verification for Milestone E:

    cd flutter-web-app
    flutter gen-l10n
    flutter analyze
    flutter test

Acceptance: widget tests cover Assisted mode anchor limit, default selected suggestions, Rakuten card rendering, import button state, and Standard mode still rendering with the existing source selector.


### Milestone F - Closet UI classification and search inclusion

Make ownership status obvious at a glance and ensure Interesting items participate in current Coordinate-from-closet.

Update `flutter-web-app/lib/closet/closet_item.dart` to parse `ownershipStatus`, `origin`, and optional external fields. Update `ClosetCard` to show two distinct visual concepts:

- analysis readiness badge: Processing / Ready / Error, as today
- ownership chip: Owned / Interesting, with separate color/icon and no spinner

Update edit UI so the user can change Interesting to Owned and Owned back to Interesting if needed. Use copy that says "Owned" / "Interesting" rather than both "purchased" and "bought".

Ensure Standard Coordinate `CLOSET` mode includes both Owned and Interesting items by relying on `status == READY`, not ownership filtering. Add tests that an Interesting READY item appears in the anchor selector and can be selected/generation-bound.

Verification for Milestone F:

    cd flutter-web-app
    flutter analyze
    flutter test

    cd firebase
    firebase emulators:exec --only firestore --project gen-fashion-local "npm test"

Acceptance: the closet grid shows a clear ownership chip; changing Interesting to Owned calls the backend and updates live through Firestore; Firestore client writes to closet remain denied; both Owned and Interesting READY items are visible/selectable for coordination.


### Milestone G - End-to-end local validation

Add a script or extend `scripts/m5_coordination_browser_e2e.py` with an Assisted mode path. It may mock Rakuten at the adapter level for deterministic CI-style validation, but there should also be a manual live-Rakuten checklist when credentials are configured.

E2E flow:

1. Start local stack with `make dev`.
2. Ensure MinIO bucket exists and at least one own closet item is READY.
3. Open Flutter Web with `make web`.
4. Choose Coordinate -> Assisted.
5. Select one to three own items.
6. Enter style preferences and start.
7. Confirm `session.proposed` returns anchor and Rakuten candidates; anchor checks stay selected and recommended checks are balanced across outfit categories.
8. Save one Rakuten suggestion to closet as Interesting.
9. Generate from selected items.
10. Confirm generated coordinate image renders and History includes selected items.
11. Go to Closet and change the saved item from Interesting to Owned.
12. Start Standard Coordinate with `CLOSET`; confirm the saved item can be selected.

Verification for Milestone G:

    make dev
    python3 scripts/m5_coordination_smoke.py --timeout-seconds 180
    python3 scripts/mk_assisted_coordinate_smoke.py --timeout-seconds 240

Acceptance: Standard M5 smoke still reaches `COMPLETED`; Assisted smoke reaches `COMPLETED`, imports a suggestion, changes ownership, and can reuse the imported item from closet.


## Concrete Steps


Working directory for all commands: `/Users/ran/my-app/gen-fashion` unless specified.

1. Implement Milestone A domain/repository mapping:

    cd fastapi-service
    python -m pytest tests/domain/test_clothing_item.py tests/adapters/test_firestore_closet_repo_mapping.py -q

2. Implement Milestone B import endpoint:

    cd fastapi-service
    python -m pytest tests/test_closet_routes.py tests/use_cases/test_closet_use_cases.py -q

3. Implement Milestone C Rakuten ADK tool with mocked API tests:

    cd adk-agent-service
    python -m pytest styling_app/tests/test_tools.py styling_app/tests/test_agents.py styling_app/tests/test_registry.py -q

4. Implement Milestone D Assisted session route and ADK execution:

    cd fastapi-service
    python -m pytest tests/use_cases/test_styling_use_cases.py tests/test_session_routes.py -q

    cd adk-agent-service
    python -m pytest styling_app/tests/test_run_session_endpoint.py styling_app/tests/test_event_normalizer.py -q

5. Implement Milestone E/F Flutter UI:

    cd flutter-web-app
    flutter gen-l10n
    flutter analyze
    flutter test

6. Verify Firestore rules still deny client closet writes:

    cd firebase
    firebase emulators:exec --only firestore --project gen-fashion-local "npm test"

7. Run full suites before marking MK complete:

    cd fastapi-service
    python -m pytest -q

    cd ../adk-agent-service
    python -m pytest -q

    cd ../flutter-web-app
    flutter analyze
    flutter test

8. Run browser or smoke E2E:

    make dev
    python3 scripts/m5_coordination_smoke.py --timeout-seconds 180
    python3 scripts/mk_assisted_coordinate_smoke.py --timeout-seconds 240


## Validation and Acceptance


MK is complete only when all of these are true:

- The Coordinate tab exposes Standard and Assisted modes without regressing Standard mode.
- Assisted mode enforces 1..3 own READY anchor clothes. Attempts with 0, 4, missing, non-owner, or non-READY item ids fail before ADK launch.
- The agent proposes text styling suggestions plus image-backed Rakuten item/accessory cards.
- Recommended suggestions are checked by default; users can change check marks before generation.
- Users can edit preferences and rerun proposal before generation without corrupting a `PROPOSING` session.
- Generation uses only server-held selected image URLs and reaches `COMPLETED` through the existing generate phase.
- A Rakuten suggestion can be saved to the user's closet as `ownershipStatus=INTERESTING`.
- The closet UI distinguishes analysis status from ownership status at a glance.
- The user can change `INTERESTING` to `OWNED`, and the change persists through Firestore and ES metadata update.
- Standard Coordinate `CLOSET` mode can select both Owned and Interesting READY items.
- Rakuten credentials are never exposed to Flutter.
- `fastapi-service` pytest, `adk-agent-service` pytest, `flutter analyze`, `flutter test`, and Firestore rules tests pass.
- A local smoke or browser E2E demonstrates Assisted propose -> selection -> generation -> save suggestion -> ownership change -> reuse from closet.


## Idempotence and Recovery


Domain and route changes are additive. Existing closet documents default to `OWNED` if `ownershipStatus` is missing, so no destructive migration is needed for local emulator data.

Importing a Rakuten suggestion should generate a new UUID closet item id each time. If an import fails after the R2 image is written but before Firestore create, rerunning the import creates a new object; cleanup can safely delete orphaned `{uid}/closet/{uuid}.jpg` objects if discovered. If Firestore succeeds but ES indexing fails, log the failure and allow the user to see the item in the closet; a later metadata update can reindex it.

Rakuten API failures should not mark the session `ERROR` if the agent can still propose from anchor/context. If no external candidates are available, Assisted mode should surface a user-readable "suggestions unavailable" error and leave Standard Coordinate untouched.

Keep Firestore rules deny-write semantics for `users/{uid}/closet/*`; all closet writes remain backend Admin SDK writes. If a rule test fails because a new client write was introduced, revert that client write and route it through FastAPI.

No GCP operations are required for local implementation. If production secrets or Cloud Run env vars are later changed during deployment, update `docs/gcp-cheatsheet.md` in that deployment change, not in this local feature plan.


## Artifacts and Notes


Current code evidence gathered while authoring:

- `flutter-web-app/lib/coordination/coordination_screen.dart` already has current source controls, candidate checkboxes, selected candidate submission, and result rendering.
- `fastapi-service/app/use_cases/styling/select_candidates.py` already enforces explicit candidate ids and passes the exact selected item objects into generate.
- `adk-agent-service/styling_app/adapters/image_storage.py` can fetch external HTTP(S) images, so generation can use Rakuten images before import.
- `fastapi-service/app/domain/closet/value_objects.py` has no ownership state yet.
- Official Rakuten docs checked on 2026-07-03: `https://webservice.rakuten.co.jp/documentation/ichiba-item-search` documents Ichiba Item Search version `2026-07-01`, endpoint `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701`, and application/access-key requirements.


## Interfaces and Dependencies


- FastAPI routes:
  - existing: `POST /sessions`, `POST /sessions/{id}/source`, `POST /sessions/{id}/select`, `GET /sessions/{id}/stream`
  - new: `POST /sessions/{id}/assist`
  - existing extended: `PATCH /closet/items/{id}` accepts ownership status
  - new: `POST /closet/import-suggestion`

- Firestore:
  - `users/{uid}/closet/{itemId}` adds `ownershipStatus`, `origin`, `externalItemId`, `externalUrl`, `affiliateUrl`, `price`, and `brandOrShop`
  - `sessions/{sessionId}` adds `coordinationMode` and `anchorItems`
  - `proposedCandidates` may include mixed `source` values and Rakuten fields

- Elasticsearch:
  - `clothing_items` mapping adds keyword fields for `ownershipStatus`, `origin`, `externalItemId`, and external URL fields. Existing search remains READY-item driven by what is indexed.

- ADK tools:
  - existing `search_closet` remains own/shared closet search
  - new `search_rakuten` handles Rakuten Ichiba item search
  - existing `style_synthesizer` remains the only generation tool

- External service:
  - Rakuten Ichiba Item Search API, official docs at `https://webservice.rakuten.co.jp/documentation/ichiba-item-search`
  - required secrets: `RAKUTEN_APPLICATION_ID`, `RAKUTEN_ACCESS_KEY`
  - optional secret: `RAKUTEN_AFFILIATE_ID`

- Flutter:
  - existing `image_picker`, `cloud_firestore`, `http`, `url_launcher` are sufficient; no new UI dependency is required.
