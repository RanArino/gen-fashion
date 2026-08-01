# Phase 2 Feature Matrix — gen-fashion

> **Source of truth:** [req-phase02.md](req-phase02.md)

---

> **Assisted Coordinate planning (2026-07-03):** Added new milestone **MK**
> for the second Web Coordinate mode requested by the user: up to three own
> anchor clothes, Rakuten-backed item/accessory suggestions, default checked
> recommendations balanced to one item per outfit category, save suggestion as
> Interesting, ownership transition to Owned, and reuse of Interesting items in
> closet-based Coordinate. ExecPlan:
> [20260703-mk-assisted-coordinate-mode.md](plans/20260703-mk-assisted-coordinate-mode.md).
> Rows **MK-1...MK-8** are ✅ as of 2026-07-03: backend, ADK, and Flutter code
> landed with tests, and local smokes pass — including live Rakuten
> suggestions (`mk_assisted_coordinate_smoke.py --require-rakuten`). The
> earlier 403 was the migrated endpoint requiring `Origin`/`Referer` headers
> (`RAKUTEN_APPLICATION_URL`), not invalid keys; the flow still degrades to
> anchor/closet-only suggestions if Rakuten is unavailable.
>
> **Rakuten metadata planning (2026-07-07):** Added milestone **MQ** for
> preserving AI-provided English search tags from `search_rakuten` candidates
> into saved `INTERESTING` closet items, without stuffing those tags into the
> Rakuten query and hurting recall. ExecPlan:
> [20260707-mq-rakuten-search-tags-for-interesting-items.md](plans/20260707-mq-rakuten-search-tags-for-interesting-items.md).
> Rows **MQ-1...MQ-5** are ✅ Completed as of 2026-07-07: ADK/FastAPI/Flutter
> regression tests pass, and live UI verification confirmed saved Interesting
> items show the English tags supplied with the Rakuten search metadata.

---

## MG — Client-Side Routing & Browser Navigation

**Scope:** Make Flutter Web navigation URL-addressable so the browser back/forward buttons, deep links, and refresh-to-view all work. Today `flutter-web-app/lib/main.dart` is `MaterialApp(home: AuthGate())`, `AuthGate` flips `LoginScreen` ↔ `HomeScreen` off `authStateChanges`, and `HomeScreen` (`lib/home/home_screen.dart`) switches the Closet / Coordinate / History / Shared views with an `int _index` + `NavigationBar` only — the URL never leaves `/`, so the Chrome back button does nothing (`ToDo`: "no concept of page paths → back button broken → poor UX"). Adopt **go_router** + `usePathUrlStrategy()`, a **ShellRoute** to keep the persistent `NavigationBar`, and go_router `redirect` for auth gating. App behavior is unchanged; only the URL representation of navigation and browser-history integration are added. Reference: `req-phase01.md` §20, ADL-033. Firebase Hosting SPA fallback is already in place (`firebase.json` `rewrites: ** → /index.html`), so deep links won't 404.

> **Tracking only (2026-06-30):** rows added at the requirements level; **no ExecPlan authored yet** per "one ExecPlan at a time" (MD is the active ExecPlan, currently at Milestone E). The MG ExecPlan is authored after MD completes. No routing dependency exists in the repo today (`go_router` is absent from `flutter-web-app/pubspec.yaml`; navigation is `int _index` state only). This change is req/matrix tracking only — no code.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MG-1 | Routing foundation (path URL strategy + Router) | ❌ Not yet implemented | Add `go_router` to `pubspec.yaml`; call `usePathUrlStrategy()` in `main()`; replace `MaterialApp(home:)` with `MaterialApp.router`. URL changes per view and reload restores the same view. | §20.1, ADL-033 |
| MG-2 | Auth-aware routing (login redirect) | ❌ Not yet implemented | Move `AuthGate`'s `authStateChanges` decision into a go_router `redirect` + `refreshListenable`: unauthenticated → `/login`, authenticated on `/login` → app. Preserve `AppConfig.e2eAutoSignIn`. No post-sign-in flicker. | §20.2, ADL-033 |
| MG-3 | Top-level view routes (browser back/forward) | ❌ Not yet implemented | Replace `HomeScreen`'s `int _index` + `NavigationBar` with a ShellRoute over `/closet` `/coordinate` `/history` `/shared` (selected tab derived from the route; `/` → `/closet`). Chrome back/forward move between views; direct-open/reload of each path shows that view (SPA fallback). `flutter analyze` clean, `flutter test` green, browser E2E shows back-button navigation. | §20.3, ADL-033 |
| MG-4 | Detail deep links (future) | ❌ Not yet implemented | Path-parameter deep links for a coordination session (`/coordinate/{sessionId}`) and history detail (`/history/{sessionId}`). **Phase 1a out-of-scope** — the top-level view routing (MG-1…MG-3) is the UX fix; this is a future extension. | §20.4, ADL-033 |

**Exit criteria:** Switching top-level views changes the URL, and the Chrome back/forward buttons move between previously visited views; opening or reloading `/closet` `/coordinate` `/history` `/shared` directly renders that view without a 404.

---


## MK — Assisted Coordinate Mode (Web)

**Scope:** Add a second Coordinate mode that starts from 1-3 own closet anchor clothes, proposes complete styling with Rakuten-backed purchasable clothes/accessories, lets the user accept category-balanced default checked recommendations or modify selection/preferences, generates through the existing candidate-selection gate, and lets Rakuten suggestions be saved to the user's closet as Interesting / later Owned. Reference: `req-phase02.md` §3, ADL-035, ADL-036.

> **ExecPlan (2026-07-03):** [20260703-mk-assisted-coordinate-mode.md](plans/20260703-mk-assisted-coordinate-mode.md). Implemented 2026-07-03: Standard Coordinate behavior is intact, closet ownership status is separated from image-processing status, and Rakuten is a separate ADK tool (`search_rakuten`) rather than overloading `search_closet`. Live-Rakuten suggestions are verified locally (the earlier 403 was fixed by sending `Origin`/`Referer` from `RAKUTEN_APPLICATION_URL`); the assisted flow degrades to anchor-only proposals when Rakuten is unavailable.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MK-1 | Assisted session mode contract | ✅ Implemented (2026-07-03) | Add `coordinationMode=ASSISTED`, `anchorItems`, and an assisted session route while leaving Standard Coordinate default behavior unchanged. | §3, ADL-036 |
| MK-2 | Up-to-three own anchor clothes | ✅ Implemented (2026-07-03) | Flutter lets users upload/select 1-3 own READY closet items; FastAPI rejects 0, >3, non-owner, missing, or non-READY anchors before ADK launch. | §3.1 |
| MK-3 | Rakuten search adapter/tool | ✅ Implemented (2026-07-03) | Add `search_rakuten` with Rakuten Ichiba Item Search / affiliate-aware output; credentials stay server-side; tests use mocked API responses. | §3.2 |
| MK-4 | Agent text + item/accessory suggestions | ✅ Implemented (2026-07-03) | Assisted propose phase returns text styling plus image-backed clothes/accessories, not only closet garments. | §3.2 |
| MK-5 | Balanced default checked recommendations + generation gate | ✅ Implemented (2026-07-03; balanced auto-selection fix 2026-07-05; Rakuten display-count fix 2026-07-06) | Anchors stay selected by default, while only one purchasable suggestion is marked recommended/checked by default; Rakuten display candidates are still fetched at a minimum of five so users have alternatives to choose from. Users can change checks/preferences; generation reuses the existing explicit `PROPOSING` -> `/select` gate. | §3.3 |
| MK-6 | Save suggested items as Interesting | ✅ Implemented (2026-07-03) | Users can import Rakuten suggestions into their private closet as READY + `ownershipStatus=INTERESTING`, copied to R2/MinIO and indexed. | §3.4, ADL-035 |
| MK-7 | Interesting to Owned status UI and closet reuse | ✅ Implemented (2026-07-03; Rakuten link added 2026-07-04) | Closet UI clearly separates processing state from ownership state; users can change Interesting to Owned; closet-based Coordinate includes both Owned and Interesting READY items. Interesting-item closet cards now also link out to the Rakuten Ichiba product page (`ClosetItem.productUrl`, `flutter-web-app/lib/closet/closet_screen.dart`). | §3.4, §3.5, ADL-035 |
| MK-8 | Assisted Coordinate E2E | ✅ Implemented (2026-07-03; live-Rakuten smoke passed) | Local smoke/browser E2E covers anchors -> Rakuten suggestions -> selection -> generation -> save Interesting -> mark Owned -> reuse from closet. | §3.6 |

**Exit criteria:** A signed-in Web user completes the Assisted Coordinate flow end to end, imports a Rakuten suggestion as Interesting, marks it Owned, and can select it in Standard Coordinate `CLOSET` mode; FastAPI, ADK, Flutter, and Firestore rules checks pass.

---

## MQ — Rakuten Search Tags for Interesting Items

**Scope:** During Assisted Coordinate, let the agent provide a concise English `tags` list alongside each Rakuten search query, keep the actual Rakuten query broad enough for recall, and persist those tags when a user saves the candidate as an Interesting closet item. No new Gemini image analysis is added to the import path. Reference: req §3.2 / §3.4, MK follow-up.

> **ExecPlan (2026-07-07):** [20260707-mq-rakuten-search-tags-for-interesting-items.md](plans/20260707-mq-rakuten-search-tags-for-interesting-items.md). Completed 2026-07-07: `search_rakuten` accepts separate English metadata tags, assisted prompts/fallbacks pass those tags without over-constraining the Rakuten query, save-as-Interesting preserves candidate tags, tests cover tag threading and recall guardrails, and live UI verification confirmed imported Interesting items show the expected tags.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MQ-1 | `search_rakuten` tag contract | ✅ Implemented (2026-07-07) | ADK tool accepts optional English metadata tags separate from the recall-oriented Rakuten query. | §3.2 |
| MQ-2 | Agent prompt + fallback tag generation | ✅ Implemented (2026-07-07) | Assisted prompts and deterministic fallback carry concise English item tags without over-constraining the query. | §3.2 |
| MQ-3 | Candidate-to-Interesting tag persistence | ✅ Implemented (2026-07-07) | Candidate tags flow through `proposedCandidates` and `POST /closet/import-suggestion`; saved Interesting items store/index those tags and do not append localized product names. | §3.4 |
| MQ-4 | Search recall guardrails | ✅ Implemented (2026-07-07) | Tests prove metadata tags are not blindly concatenated into every Rakuten keyword variant, avoiding zero-result over-filtering. | §3.2 |
| MQ-5 | Regression tests + manual verification | ✅ Implemented (2026-07-07) | ADK/FastAPI/Flutter tests cover tag threading; live Style & Shop UI verification confirmed saved Interesting items show the expected English tags. | §3.6 |

**Exit criteria:** A Rakuten tool call can show `query` and English `tags` separately; Rakuten results still appear; saving a candidate as Interesting stores those tags in Firestore and Elasticsearch; no extra image-analysis call is required.

---

## ML — Style & Shop Trace Preview + Closet Edit Dialog UI Fixes

**Scope:** Two UI bugs reported against already-shipped milestones: (1) in Style & Shop (Assisted Coordinate) mode, the agent-trace accordion's `search_rakuten` steps rendered raw JSON even in "Preview" mode, because MJ's per-tool Preview dispatcher (`docs/plans/20260702-mj-agent-trace-preview-raw-views.md`) predates MK's `search_rakuten` tool by one day and was never extended to it; (2) the closet item edit dialog's fields (Category/Colors/Season/Tags/Gender/Ownership) had no spacing or width constraint, rendering cramped. Both are front-end-only fixes within already-tracked Assisted Coordinate scope (§3). Reference: `req-phase02.md` §3, no new ADL (see ExecPlan Decision Log).

> **ExecPlan (2026-07-04):** [20260704-ml-assisted-preview-and-closet-edit-fixes.md](plans/20260704-ml-assisted-preview-and-closet-edit-fixes.md). Implemented and verified 2026-07-04: `flutter analyze` clean, `flutter test` 43 passed (2 new), and a live browser run of an Assisted/Style & Shop session against real Rakuten data confirmed the `search_rakuten` trace steps render labeled Preview fields (query/category/colors on call; "N items found" + thumbnail/name/price/shop per item on result) with Raw still available as JSON, plus the closet edit dialog now has visible field spacing.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| ML-1 | `search_rakuten` trace preview | ✅ Implemented (2026-07-04) | `_SearchRakutenPreview`/`_RakutenItemRow` added to the `_AgentPreview` dispatcher (`coordination_screen.dart`); `AgentEvent.summary()` gains matching tile-title branches. Verified live against real Rakuten results. | §3 |
| ML-2 | Closet edit dialog spacing | ✅ Implemented (2026-07-04) | `_onEdit`'s dialog content wrapped in a 360px-wide `SizedBox` with `SizedBox(height: 12)` gaps between all six fields, matching `_SaveInterestingDialog`'s convention. No field/save behavior change. | §3.4 |

**Exit criteria:** Expanding a `search_rakuten` trace step in Preview mode shows labeled fields/items, never raw JSON (Raw still shows JSON); the closet edit dialog's fields are visibly spaced and consistently widthed.

---

## MM — Closet/Coordination Onboarding & Contextual Help UI

**Scope:** The Closet page and the Coordination result panel both always showed the CC BY-SA dataset banner even though it only applies to shared-dataset images (the Shared tab), and gave no in-app explanation of Closet's purpose, upload flow, or ownership/category filters; Coordination's mode/source segmented buttons ("Closet Styling"/"Style & Shop", "Shared"/"Mine") and the Closet "Owned"/"Interesting" ownership distinction had no hover explanation. Pure front-end/localization UI polish, no backend or data-model change. Reference: `req-phase02.md` §4, no new ADL (see ExecPlan Decision Log).

> **ExecPlan (2026-07-04):** [20260704-mm-closet-coordination-onboarding-help.md](plans/20260704-mm-closet-coordination-onboarding-help.md). Implemented and verified 2026-07-04: `flutter analyze` clean, `flutter test` 43 passed (unchanged count, all additive), and a live browser run (Playwright against a `flutter build web` release bundle, `E2E_AUTO_SIGN_IN`) confirmed the Closet banner and the Coordination result-panel banner are both gone, the new help dialog opens from both the filter bar and empty state, Coordination's four segment tooltips and the ownership filter/edit-dialog tooltips all render, in both 日本語 and English.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MM-1 | Attribution-banner removal (Closet + Coordination result) | ✅ Implemented (2026-07-04) | `AttributionFooter()` removed from both `ClosetScreen` build branches and, after user review of a live screenshot, from `_ResultPanel` (`coordination_screen.dart`) too — only the Shared tab (`shared_closet_gallery.dart`) still shows it. `_ResultPanel`'s now-unused `source` field was removed along with the now-unused `attribution.dart` import. | §4 |
| MM-2 | Closet help dialog + two entry points | ✅ Implemented (2026-07-04) | New `showClosetHelpDialog` + `_ClosetHelpButton` in `closet_screen.dart`, wired into `ClosetFilterBar`'s header and `_EmptyState`; confirmed live in both languages. | §4 |
| MM-3 | Coordination tab hover tooltips (mode+source) | ✅ Implemented (2026-07-04) | `tooltip:` added to all four `ButtonSegment`s in `coordination_screen.dart`'s `_Controls`; confirmed live via mouse-hover screenshots. | §4 |
| MM-4 | Ownership Owned/Interesting tooltips | ✅ Implemented (2026-07-04) | Tooltips on `ClosetFilterBar`'s ownership segments; live-updating caption in the edit-dialog Ownership dropdown; confirmed live, including the caption switching live when the dropdown selection changes. | §4 |
| MM-5 | Localization + verification | ✅ Implemented (2026-07-04) | 9 new ARB keys in both catalogs, `flutter gen-l10n`, `flutter analyze` clean, `flutter test` 43/43 passed, manual two-language browser check passed. | §4 |

**Exit criteria:** The Closet page's default view and the Coordination result panel no longer show the CC BY-SA banner (only the Shared tab still shows it); a "how this page works" help dialog is reachable from both the Closet filter bar and the empty state; hovering any of Coordination's four mode/source segment labels shows a tooltip; hovering the Closet ownership filter chips, and the item-edit dialog's Ownership caption, explain "Owned" vs "Interesting" — confirmed in both 日本語 and English.

---

## MN — Unified Help Accordion, Touch Parity, Language-Switcher Fix, New-User Nudge

**Scope:** Follow-up to MM after live use: hover-only tooltips don't work for touch/mobile users, the header language switcher truncated the Japanese label, the Closet-only help icon should fold into the existing global header info icon (one dialog, one Accordion section per tab, auto-expanding the current tab's section), and new/empty-closet users should be nudged toward that icon. Reference: `req-phase02.md` §4 (revised), no new ADL.

> **ExecPlan (2026-07-04):** [20260704-mn-unified-help-nudge-touch-fixes.md](plans/20260704-mn-unified-help-nudge-touch-fixes.md). Implemented and verified 2026-07-04: `flutter analyze` clean, `flutter test` 43/43 passed, and a live browser run (Playwright against a `flutter build web` release bundle with the local emulator stack) confirmed the unified accordion dialog auto-expands the correct section from Closet/Coordinate/Shared, the Shared section keeps the CC BY-SA attribution and Kaggle link with reworded demo-purpose copy, Coordination's source caption and Closet's ownership caption are now always visible (not hover-only), and the language switcher shows the full "日本語"/"English" label, in both languages.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MN-1 | Unified help accordion dialog | ✅ Implemented (2026-07-04) | New `showAppHelpDialog` (`lib/shared/help_dialog.dart`) with one `ExpansionTile` per tab (Closet/Coordinate/History/Shared), `initiallyExpanded` set to the tab the user opened it from. Retires `showSharedClosetAboutDialog`; `AttributionFooter`'s `onTap` now opens this dialog with the Shared section expanded. | §4 |
| MN-2 | Closet-only help icon retired | ✅ Implemented (2026-07-04) | Removed `_ClosetHelpButton`/`showClosetHelpDialog` from `closet_screen.dart`; the header's single global info icon (`home_screen.dart`) is now the only entry point, wired to the current tab via an index→section map. Empty-closet state shows a plain hint pointing at the header icon instead of its own tappable affordance. | §4 |
| MN-3 | Touch-safe captions replace hover-only tooltips | ✅ Implemented (2026-07-04) | Coordination's source selector and Closet's ownership filter now show an always-visible caption (mirroring the existing mode-selector caption pattern), in addition to the existing hover `tooltip:` bonus for desktop. | §4 |
| MN-4 | Language-switcher truncation fix | ✅ Implemented (2026-07-04) | Replaced `_LanguageSwitcher`'s `Chip`-wrapped label (which force-truncates via `Chip`'s internal `maxLines:1`/fade styling) with a plain icon+text `Row`, so "日本語" no longer renders as "日本...". | §4 |
| MN-5 | New-user / empty-closet nudge animation | ✅ Implemented (2026-07-04) | Header info icon pulses (`ScaleTransition` + `AnimationController`) when the closet is empty or the account was created within 24h (`users/{uid}.createdAt`); stops for the session once tapped. Session-only, no new dependency. | §4 |
| MN-6 | Localization + verification | ✅ Implemented (2026-07-04) | New ARB keys (`appHelpTooltip`, `appHelpTitle`, `helpCoordinateIntro`, `helpHistoryBody`, `emptyClosetHelpHint`), reworded `sharedAboutBody` to state the shared closet's demo purpose, removed now-unused `sharedClosetAbout`/`closetHelpTooltip`/`closetHelpTitle` keys, `flutter gen-l10n`, `flutter analyze` clean, `flutter test` 43/43 passed, manual two-language browser check passed. | §4 |

**Exit criteria:** One header info icon opens a single dialog with four Accordion sections, auto-expanding the section for the tab it was opened from; Coordination's source caption and Closet's ownership caption are visible without hovering; the language switcher shows the full "日本語"/"English" label; the header icon visibly pulses when the closet is empty or the account is new, and stops after being tapped for that session — confirmed in both 日本語 and English.

---

## MO — Scene-Aware Style Synthesizer Prompt (Rakuten Non-Garment Photo Robustness)

**Scope:** Assisted/Style & Shop (MK) coordinate generation degrades when a Rakuten product photo is not a clean single-garment shot (person wearing the garment, hand holding an item amid props). Phase 1 fix only: label each reference image with its garment/accessory category and instruct the generation model to extract only that labeled item, ignoring any person/background/pose/unrelated object in the photo. No image selection, classification, or cropping (deferred). Reference: `docs/local/20260704_styling_image_generation_issue.md`, `req-phase01.md` §6.5/§7.2, ADL-005 (model constraint unchanged), no new ADL.

> **ExecPlan (2026-07-04):** [20260704-mo-style-synthesizer-scene-aware-prompt.md](plans/20260704-mo-style-synthesizer-scene-aware-prompt.md). Implemented 2026-07-04 (MO-1..MO-5): `pytest adk-agent-service/styling_app/tests -q` → 60 passed. Follow-up fix 2026-07-06: the production generate paths now pass selected item categories into `style_synthesizer`; after a regression where an over-constrained prompt caused `collage-fallback`-quality output, the prompt was shortened and generation now retries once with a compact prompt. Collage output is no longer accepted as a completed coordinate. **2026-07-11:** MO-6 run live against a real `make dev` stack + live Vertex AI/Rakuten credentials (`scripts/mo6_scene_aware_visual_check.py`, session `a23e65b0-4561-45e4-9bbe-eb2047347231`) — PASS. See the ExecPlan's Outcomes section for the observed per-input-type result.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MO-1 | Per-item labeled reference images | ✅ Implemented (2026-07-04) | `image_generation.generate()` takes `list[{bytes, category, note}]` and inserts a labeled text part before each image part. | §6.5 |
| MO-2 | Scene-extraction prompt instruction | ✅ Implemented (2026-07-04) | `_TRYON_PROMPT` explicitly tells the model to extract only the labeled item per photo and ignore person/background/pose/unrelated objects. | §6.5 |
| MO-3 | `style_synthesizer` category forwarding | ✅ Implemented (2026-07-04) | New optional `item_categories` param, parallel to `item_image_urls`, threaded into `image_generation.generate()`. | §7.2 |
| MO-4/5 | Unit + integration test coverage | ✅ Implemented (2026-07-04) | `test_image_generation.py` (label placement) + `test_tools.py` additions proving a `search_rakuten` result's `category` reaches the `generate()` call via `style_synthesizer`. | §6.5, §7.2 |
| MO-6a | Production category propagation + retry prompt | ✅ Implemented (2026-07-06) | Fixed the missing production wiring: `_build_generate_style_tool` and `_run_generate_fallback` now pass server-authoritative selected item categories into `style_synthesizer`; prompt was shortened to avoid degrading generation quality, and `style_synthesizer` retries once with a compact prompt. If generation still fails, the session errors instead of saving a collage as the completed coordinate. | §6.5, §7.2 |
| MO-6 | Manual visual check | ✅ Verified (2026-07-11) | Live Assisted Coordinate session (`scripts/mo6_scene_aware_visual_check.py`, session `a23e65b0-4561-45e4-9bbe-eb2047347231`) selected 3 real Rakuten reference photos — a person-wearing-it-plus-holding-a-bag-plus-text/badge-overlay photo (white pants), a plain product shot (sneakers), and a staged prop scene with text overlays (tote bag) — alongside a synthetic anchor. Generated coordinate reproduced each item's correct color/shape on one fresh model with no leaked original models, text, badges, or backgrounds. Evidence: `/tmp/mo6-evidence-run2/`. | §6.5 |

**Exit criteria:** `pytest adk-agent-service/styling_app/tests` passes with the new/updated tests (met); a manual generation run against realistic person-worn/staged-prop Rakuten inputs shows the original model/background/props visibly reduced or absent compared to the pre-change prompt (met — 2026-07-11).

---

## MP — Coordinate Session Persistence & Completion Notification

**Scope:** Keep Coordinate's agent trace/candidates/generated image alive across in-app tab navigation; notify the user in-app when generation completes off-tab; make the completed Coordinate state clearly actionable for starting a new styling session; harden the Cloud Run deploy so background generation isn't CPU-starved after the triggering request completes. Reference: `req-phase02.md` §5, ADL-037.

> **ExecPlan (2026-07-05):** [20260705-mp-coordinate-session-persistence.md](plans/20260705-mp-coordinate-session-persistence.md). Authored and implemented 2026-07-05; investigation confirmed the backend (`adk-agent-service`) already runs generation asynchronously via FastAPI `BackgroundTasks`, independent of the browser connection — the bug was entirely client-side (`HomeScreen` destroyed `CoordinationScreen`'s state on every tab switch) plus a Cloud Run deploy-config gap (no `--no-cpu-throttling`). MP-1...MP-6 landed with `flutter analyze` clean and `flutter test` 49 passed (43 pre-existing + 6 new); MP-8 follow-up added a completed-state "Start a new coordinate" CTA and brought Flutter tests to 51/51; `fastapi-service` pytest 109 / `adk-agent-service` pytest 60 unaffected (no backend files touched). **2026-07-11 audit:** live `adk-agent-service` has `run.googleapis.com/cpu-throttling: 'false'`. MP-7's automated tests and post-deploy Cloud Run check are done; the local `make dev` manual browser pass remains open. **2026-07-11 local browser pass:** a scripted headless-Chrome run (`scripts/mp7_tab_persistence_browser_e2e.py`, session `6f55877f-2988-44f6-9ffd-ee0d2aa6c832`) against a live `make dev` stack confirmed all remaining manual checks — tab-switch state preservation, the off-tab SnackBar + working "View" action, and History's live refresh. MP-7 is now fully done; see its row below for details.

| ID | Feature | Status | Description | Req ref |
|---|---|---|---|---|
| MP-1 | Keep-alive tabs | ✅ Implemented (2026-07-05) | Lazy `IndexedStack` in `HomeScreen` (`_visitedTabs`) keeps all four tabs' `State` mounted once visited. | §5, ADL-037 |
| MP-2 | Terminal-state callback | ✅ Implemented (2026-07-05) | `CoordinationScreen.onSessionTerminal` fires once per session on `COMPLETED`/`ERROR` via `_maybeNotifyTerminal`. | §5 |
| MP-3 | Bounded recovery poll | ✅ Implemented (2026-07-05) | One-shot post-SSE resync replaced by a bounded `GET /sessions/{id}` poll (gated on `status != 'GENERATING'`); save-Interesting dialog reordered to only fire after resolved `COMPLETED`. | §5 |
| MP-4 | History live refresh | ✅ Implemented (2026-07-05); manually verified 2026-07-11 | `HistoryScreen`'s new `refreshOn` listenable refetches on an off-tab completion signal, avoiding keep-alive staleness. Live check: History visited pre-completion (empty state screenshot), then showed the newly-`COMPLETED` session after off-tab generation finished, with no page reload (`docs/local` evidence: `/tmp/mp7-evidence-run2/04_history_tab_first_visit.png` → `10_history_after_completion.png`). | §5 |
| MP-5 | SnackBar notification | ✅ Implemented (2026-07-05); manually verified 2026-07-11 | `HomeScreen._handleSessionTerminal` shows a SnackBar with a "View" action when off-tab; new en/ja l10n strings (`coordinateReadyNotification`/`coordinateFailedNotification`/`viewAction`). Live check: off-tab `COMPLETED` produced the SnackBar ("コーディネートが完成しました。" / "表示", screenshot `/tmp/mp7-evidence-run2/06_snackbar_pre_click.png`), and clicking "View" navigated back to Coordinate showing the completed trace (`07_after_view_click_attempts.png`). | §5 |
| MP-6 | Cloud Run CPU fix | ✅ Implemented (2026-07-05; live check 2026-07-11) | `--no-cpu-throttling` added to `adk-agent-service`'s deploy (`scripts/deploy/deploy_adk.sh`); `bash -n` verified. Live Cloud Run now reports `run.googleapis.com/cpu-throttling: 'false'`. | §5 |
| MP-7 | Tests + manual verification | ✅ Verified (2026-07-11) | 6 new `coordination_screen_test.dart` cases + new `tab_persistence_test.dart` all pass (`flutter test` 51/51; audit: 61 passed). Post-deploy Cloud Run CPU-throttling check done (MP-6). Local `make dev` manual browser pass done via `scripts/mp7_tab_persistence_browser_e2e.py` (session `6f55877f-2988-44f6-9ffd-ee0d2aa6c832`): Closet→History→Coordinate mid-`GENERATING` preserved trace/candidate state (same `sessionId`, `eventCount` 22→23, screenshots `02_generating_on_tab.png`/`05_back_to_coordinate.png` visually identical); off-tab completion produced exactly one SnackBar with a working "View" action (see MP-5 row); History showed the new session live (see MP-4 row). Full evidence: `/tmp/mp7-evidence-run2/`. | §5 |
| MP-8 | Completed-state new session CTA | ✅ Implemented (2026-07-05) | Completed Coordinate results now show localized completion copy plus "Start a new coordinate"; activating it clears the completed session trace/candidates/result/status while preserving the user's current mode and preference inputs. | §5 |

**Exit criteria:** Switching tabs mid-generation and back preserves the trace/candidates/image (met — 2026-07-11 live check); a SnackBar appears with a working "View" action when generation completes off-tab, exactly once per session (met — 2026-07-11 live check); a completed off-tab session appears in History without a reload (met — 2026-07-11 live check); the completed Coordinate page offers a clear new-session action (met, MP-8); `flutter analyze`/`flutter test` pass (met); the Cloud Run deploy carries `--no-cpu-throttling` (met — verified post-deploy 2026-07-11).

---
