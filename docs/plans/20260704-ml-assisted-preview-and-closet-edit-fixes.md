# ML — Style & Shop Trace Preview + Closet Edit Dialog UI Fixes

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.

## Context

Two UI bugs were reported (`ToDo` lines 39-40, screenshots attached by the user):

1. In **Style & Shop mode** (the Assisted Coordinate mode's English label, `modeAssisted` = "Style & Shop" / アシスト "買い足し提案"), expanding an agent-trace accordion step shows a raw, indented JSON dump even though the tile defaults to "Preview" mode. This is a regression gap, not a new bug class: milestone **MJ** (`docs/plans/20260702-mj-agent-trace-preview-raw-views.md`) built the Preview/Raw toggle and added per-tool formatters for `search_closet`, `style_synthesizer`, `transfer_to_agent`, and `final_answer` — but MJ shipped on 2026-07-02, one day *before* milestone **MK** (`docs/plans/20260703-mk-assisted-coordinate-mode.md`) added the `search_rakuten` tool for Assisted/Style & Shop mode. `search_rakuten` was never added to the Preview dispatcher, so its `tool_call`/`tool_result` events fall through to the JSON-fallback branch — the exact "unreadable raw blob" MJ was written to eliminate, just for a tool that didn't exist yet when MJ was written.

2. In the **Closet** screen, clicking an item's edit (pencil) icon opens a metadata dialog (`_onEdit` in `closet_screen.dart`) whose fields (Category, Colors, Season, Tags text fields + Gender/Ownership dropdowns) are stacked in a bare `Column` with **zero spacing** between them and no dialog width constraint — they render visually cramped/jammed together. This dialog predates the ownership dropdown added in MK-6 and was never revisited for layout. Every other dialog in this codebase (e.g. `_SaveInterestingDialog` in `coordination_screen.dart`) uses a `SizedBox(width: 360)` content constraint plus `SizedBox(height: 12)` gaps between elements — this dialog is the outlier.

Both are front-end-only presentation fixes: no backend, ADK, or data-model change, and no new architecture component (the `search_rakuten` tool/adapter is already documented in `docs/architecture-overview.md` as p11 under MK). Fixing them just extends an already-established pattern (MJ's per-tool preview formatter, and the app's established dialog-spacing convention) to code that didn't follow it yet.

**Note for the user:** while researching this, I found that milestones **MI** and **MJ** were never actually added to `docs/feature-matrix-phase01.md` or referenced in `docs/req-phase01.md` (the MJ ExecPlan cites "req-phase01.md §24, ADL-037", but no such section/ADL exists in that file) — a pre-existing sync gap unrelated to this task. I'm not fixing that backfill here since it's out of scope for this bug fix, but flagging it since it's exactly the kind of drift the matrix-sync rule exists to prevent.

## Progress

- [x] (2026-07-04) ML-1 — Added `_SearchRakutenPreview`/`_RakutenItemRow` to the `_AgentPreview` dispatcher (`coordination_screen.dart`) plus `AgentEvent.summary()` branches for `search_rakuten` call/result tile titles.
- [x] (2026-07-04) ML-2 — Wrapped the closet edit dialog content in `SizedBox(width: 360)` and added `SizedBox(height: 12)` gaps between all six fields, matching `_SaveInterestingDialog`'s convention.
- [x] (2026-07-04) ML-3 — Added `traceQuery`/`traceShopName`/`traceSearchingRakuten`/`traceSearchedRakuten` to both ARB catalogs, regenerated via `flutter gen-l10n`. `flutter analyze` clean; `flutter test` 43 passed (2 new widget tests added for the Rakuten call/result Preview, asserting the labeled fields render and no raw-JSON substring like `"item_id"` appears). Manual browser verification against `make dev` + a static `flutter build web` bundle: ran a live Assisted/Style & Shop session (real Rakuten data, not degraded), expanded `search_rakuten` call and result trace tiles — Preview showed Query/Category/Colors on the call and "N items found" + thumbnail/name/price/shop rows on the result; toggling to Raw still showed indented JSON. The closet edit dialog was opened live and confirmed to have visible spacing between all six fields.

## Surprises & Discoveries

- Observation: `flutter run -d chrome` (DWDS debug mode) served a page that stayed blank white when driven from a second, separately-launched Playwright browser — the debug session appears keyed to the one Chrome tab `flutter run` itself launches, so a fresh navigation from another browser never got `main()` to run visibly. Switched to `flutter build web` (release bundle) served via a plain `python3 -m http.server`, which Playwright rendered correctly.
  Evidence: `flutter run -d chrome` + Playwright `page.goto` → blank screenshot after 15s wait, no console errors, no page errors. `flutter build web` + `http.server` + the same Playwright script → full app render on first screenshot.
- Observation: this Flutter Web build (CanvasKit renderer) draws text to canvas pixels only; Playwright's text-based locators (`getByText`) and `page.locator('body').innerText()` do not see that text at all, so text-based waits/clicks time out or silently miss content that is clearly visible in screenshots.
  Evidence: `getByText('買い足し提案')` and `getByText(/検索しました/)` both hit 30s timeouts despite the labels being visibly rendered in screenshots taken moments later; `innerText()` polling for `'楽天'` never matched even after the text was on-screen. Worked around by clicking fixed pixel coordinates read off prior screenshots instead of text/role-based locators.

## Decision Log

- Decision: No new ADL / `docs/architecture-overview.md` update.
  Rationale: `search_rakuten` is already a documented component (architecture-overview.md line ~240, "RakutenSearchPort / search_rakuten tool (MK)"); this change only teaches the existing Flutter trace-preview dispatcher how to render its already-flowing data. No component, port/adapter, store, or endpoint is added, removed, or rewired, and nothing moves across the implemented/planned boundary — same reasoning MJ itself used.
  Date/Author: 2026-07-04 / ExecPlan

- Decision: Track both fixes under a new milestone **ML** in `docs/feature-matrix-phase02.md`, referencing `req-phase02.md` §3 (the existing Assisted Coordinate Mode section), rather than inventing new req prose or a new ADL.
  Rationale: Both bugs are gaps in already-specified behavior (MJ's "no raw JSON in Preview" requirement; the closet edit dialog's already-shipped ownership UI from MK-6), not new requirements. `req-phase02.md` §3 already covers the Assisted Coordinate mode and closet ownership UI these fixes belong to.
  Date/Author: 2026-07-04 / ExecPlan

## Outcomes & Retrospective

**Completed 2026-07-04.** Both ML-1 and ML-2 landed in `flutter-web-app/lib/coordination/coordination_screen.dart` and `flutter-web-app/lib/closet/closet_screen.dart`, with ARB keys in both catalogs. `flutter analyze` clean; `flutter test` 43 passed (up from 41, +2 new). Live browser verification against a real Assisted Coordinate session (live Rakuten API, not the degraded fallback) showed the `search_rakuten` trace steps rendering a proper Preview — Query/Category/Colors chips on the call, "N items found" + thumbnail/name/price/shop rows on the result — with Raw still available as indented JSON, and accordion tile titles reading "ClosetAgent が楽天を検索中" / "...検索しました - N 件" instead of the old generic fallback. The closet edit dialog was opened live and now shows clear spacing between all six fields. `docs/feature-matrix-phase02.md` updated with a new **ML** milestone (rows ML-1/ML-2) referencing this ExecPlan and `req-phase02.md` §3; no ADL or architecture-overview change was needed (see Decision Log).

## Context and Orientation

All Flutter work is in `flutter-web-app/lib/coordination/coordination_screen.dart` (trace preview) and `flutter-web-app/lib/closet/closet_screen.dart` (edit dialog), plus the ARB catalogs.

**Trace preview dispatcher** (`coordination_screen.dart:987-1013`, `_AgentPreview`): a `StatelessWidget` that switches on `event.toolName` / `event.eventKind`:

    if (event.toolName == 'search_closet') return _SearchClosetPreview(...);
    if (event.toolName == 'style_synthesizer') return _StyleSynthesizerPreview(...);
    if (event.toolName == 'transfer_to_agent') return ...;
    if (event.eventKind == 'final_answer') return _FinalAnswerPreview(...);
    return SelectableText(JsonEncoder.withIndent('  ').convert(event.toJson()), ...); // fallback

`search_rakuten` (added by MK, `adk-agent-service/styling_app/tools/search_rakuten.py`) hits the fallback branch. Its shapes:

- **call args:** `{query, category, colors, limit}` (see `search_rakuten(query, category=None, colors=None, limit=5)`).
- **result:** a list under `toolResult['result']` (same ADK function-response wrapping convention as `search_closet`, confirmed by `server.py` always emitting `tool_result={"result": ...}`), each item shaped `{item_id, source: "RAKUTEN", name, image_url, price, category, tags, external_url, affiliate_url, shop_name, attribution}`.

The existing `_SearchClosetPreview` (`:1016-1068`) and its helper `_ClosetItemRow` (`:1201-1273`) are the direct model to mirror: call → labeled fields via `_PreviewField`/`_ChipRow` (`:1143-1200`), result → a "N items found" header (`l10n.traceItemsFound`) + a compact per-item row with a 48×48 thumbnail. The existing `CandidateCard` (`:1351-1488`) already renders Rakuten fields for the *candidate selection* UI (name, `'¥$price'` literal — no l10n key for currency, `externalUrl` from `affiliate_url ?? external_url`), so the new preview row should use the same field names/format for consistency, while omitting `item_id`, `source`, `external_url`, `affiliate_url`, and `attribution` — the same "machine noise omitted, human-meaningful fields shown" rule MJ applied to `search_closet`.

`AgentEvent.summary()` (`:1678-1693`) also has no branch for `search_rakuten`, so its accordion tile title currently falls back to the generic `'$agentName · $eventKind'` — the same gap, one level up (title, not body). Fix both in the same change since they're the same root cause.

**Closet edit dialog** (`closet_screen.dart:117-223`, `_onEdit`): an `AlertDialog` with `content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [TextField, TextField, TextField, TextField, DropdownButtonFormField, DropdownButtonFormField]))` — no `SizedBox` gaps between the six fields, no width constraint. Compare to the established convention in `_SaveInterestingDialog` (`coordination_screen.dart:1512-1554`): `content: SizedBox(width: 360, child: SingleChildScrollView(child: Column(..., children: [..., const SizedBox(height: 12), ...])))`.

## Plan of Work

### ML-1 — `search_rakuten` trace preview

1. In `_AgentPreview.build` (`coordination_screen.dart:993`), add a branch: `if (event.toolName == 'search_rakuten') return _SearchRakutenPreview(event: event, l10n: l10n);` — placed alongside the `search_closet` branch.
2. Add `_SearchRakutenPreview` (mirrors `_SearchClosetPreview`'s structure):
   - `tool_call`: `_PreviewField` rows for Query (`args['query']`), Category (`args['category']`), Colors (`args['colors']` as `_ChipRow`); skip `limit` (matches `search_closet`'s call formatter hiding `limit`).
   - `tool_result`: header via `l10n.traceItemsFound(items.length)` (reuse, count-aware, already exists) + a list of a new `_RakutenItemRow` per item.
3. Add `_RakutenItemRow` (mirrors `_ClosetItemRow`'s 48×48-thumbnail-plus-details layout, using `webHtmlElementStrategy: WebHtmlElementStrategy.prefer` for the thumbnail `Image.network` the same way `CandidateCard`/`_SaveInterestingDialog` already do for Rakuten CDN images — otherwise the thumbnail will silently fail with the known CORS `statusCode: 0` issue documented in the MK plan's Surprises section): shows Name, `'¥$price'` (only if `price != null`, matching `CandidateCard`), Category, and Colors/Tags via `_ChipRow`; omits `item_id`, `source`, `external_url`, `affiliate_url`, `shop_name`... — actually include Shop (new field, not shown elsewhere) as a small secondary line since it's a human-meaningful "who sells this" fact, distinct from the machine-noise fields (URLs/ids/attribution) that stay omitted.
4. In `AgentEvent.summary()` (`:1678`), add branches mirroring the `search_closet` pair:

       if (toolName == 'search_rakuten' && eventKind == 'tool_result') {
         final raw = toolResult?['result'];
         final count = raw is List ? raw.length : 0;
         return l10n.traceSearchedRakuten(agentName, count);
       }
       if (toolName == 'search_rakuten') {
         return l10n.traceSearchingRakuten(agentName);
       }

### ML-2 — Closet edit dialog layout

5. In `_onEdit` (`closet_screen.dart:126-196`), wrap the `content` in `SizedBox(width: 360, child: SingleChildScrollView(...))` (matching `_SaveInterestingDialog`'s constraint) and insert `const SizedBox(height: 12)` between each of the six fields (Category, Colors, Season, Tags, Gender dropdown, Ownership dropdown). No field logic, validation, or save behavior changes — purely spacing/width.

### ML-3 — Localize + verify

6. Add ARB keys to `lib/l10n/app_en.arb` and `lib/l10n/app_ja.arb` (default catalog is `app_ja.arb` per MJ's established convention): `traceQuery` ("Query" / "検索キーワード"), `traceShopName` ("Shop" / "店舗"), `traceSearchingRakuten` ("{agentName} is searching Rakuten" / "{agentName} が楽天を検索中"), `traceSearchedRakuten` ("{agentName} searched Rakuten - {count} candidates" / "{agentName} が楽天を検索しました - {count} 件") with `agentName`/`count` placeholders mirroring `traceSearchedCloset`'s exact placeholder block. Reuse existing keys `category`, `colors`, `traceTags`, `traceItemsFound` — no new keys needed for those.
7. Run `flutter gen-l10n`, `flutter analyze`, `flutter test`.
8. Manual browser check against `make dev`: run a Style & Shop (Assisted) coordination, expand the `search_rakuten` accordion step, confirm Preview shows Query/Category/Colors (call) and "N items found" + thumbnail/name/price/shop/category/colors rows (result) — not JSON — and Raw still shows JSON. Confirm the tile title reads "searching Rakuten" / "searched Rakuten - N candidates" instead of the generic fallback. Separately, open the closet, click a card's edit icon, and confirm the six fields now have visible gaps and the dialog isn't oddly wide/narrow. Check both `日本語` and `English`.

## Concrete Steps

Working directory: `/Users/ran/my-app/gen-fashion/flutter-web-app`.

    flutter gen-l10n
    flutter analyze          # expect: No issues found
    flutter test             # expect: green, existing 41 tests + any new ones

## Validation and Acceptance

- Expanding a `search_rakuten` step in Style & Shop mode's trace accordion, in Preview mode, shows labeled fields and per-item rows — never raw JSON. Switching to Raw still shows indented JSON (unchanged fallback behavior).
- The `search_rakuten` accordion tile title is a readable sentence ("... is searching Rakuten" / "... searched Rakuten - N candidates"), not `agentName · eventKind`.
- The closet edit dialog's six fields have visible vertical spacing and a consistent width, matching `_SaveInterestingDialog`'s look; saving still calls `updateItemMetadata` with the same payload as before (no behavior change, only layout).
- `flutter analyze` clean; `flutter test` green; two-language (日本語/English) manual browser check passes for both fixes.

## Idempotence and Recovery

Both changes are additive/cosmetic Dart + ARB edits with no backend, contract, or data-model impact. If `_SearchRakutenPreview` encounters an unexpected shape it has no special fallback of its own — but it's only ever reached for `toolName == 'search_rakuten'`, and unknown/malformed fields simply render as absent (`if (x != null)` guards), never crash. Re-run `flutter gen-l10n` if the generated localization files are stale. Reverting is a plain `git checkout` of the two Dart files and two ARB files.

## Artifacts and Notes

Files expected to change:

    flutter-web-app/lib/coordination/coordination_screen.dart   (_AgentPreview branch, _SearchRakutenPreview, _RakutenItemRow, AgentEvent.summary() branches)
    flutter-web-app/lib/closet/closet_screen.dart                (_onEdit dialog spacing/width)
    flutter-web-app/lib/l10n/app_en.arb                          (traceQuery, traceShopName, traceSearchingRakuten, traceSearchedRakuten)
    flutter-web-app/lib/l10n/app_ja.arb                          (same keys, Japanese)
    flutter-web-app/lib/l10n/app_localizations*.dart             (regenerated by flutter gen-l10n)
    docs/feature-matrix-phase02.md                                (new ML milestone, rows ML-1/ML-2, referencing this ExecPlan and req-phase02.md §3)

No changes in `fastapi-service/` or `adk-agent-service/`; no `docs/architecture-overview.md` change (see Decision Log).

## Interfaces and Dependencies

| Name | Location | Purpose |
|---|---|---|
| `_AgentPreview` | `flutter-web-app/lib/coordination/coordination_screen.dart` | Dispatcher gaining a `search_rakuten` branch |
| `_SearchRakutenPreview` / `_RakutenItemRow` (new) | same file | Human-readable rendering of `search_rakuten` call/result, mirroring `_SearchClosetPreview`/`_ClosetItemRow` |
| `AgentEvent.summary()` | same file | Gains `search_rakuten` title branches mirroring `search_closet`'s |
| `_onEdit` closet dialog | `flutter-web-app/lib/closet/closet_screen.dart` | Gains width constraint + inter-field spacing, matching `_SaveInterestingDialog`'s convention |
| `AppLocalizations` / ARB catalogs | `flutter-web-app/lib/l10n/*.arb` → generated | New `traceQuery`/`traceShopName`/`traceSearchingRakuten`/`traceSearchedRakuten` keys |
