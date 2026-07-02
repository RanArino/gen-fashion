# MJ — Agent Trace Preview / Raw Views (User-Friendly Accordion)


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


While the agents work, the Coordination screen shows a live accordion (one `ExpansionTile` per agent step). Today, expanding a tile dumps a raw, developer-only blob — a Dart-map `toString()` of the event (`args: {…}`, `result: {…}`) that is not even valid JSON and, for the Closet Agent, inlines every retrieved item plus its image URL. It is unreadable for a normal user and noisy even for a developer.

This ExecPlan makes each accordion item switchable between two views:

1. **Preview (user-friendly)** — a small, labeled, per-tool rendering that shows only the human-meaningful fields. This is the **default**.
2. **Raw (developer)** — the full event as pretty-printed, indented JSON.

The toggle is **per accordion item** (each tile remembers its own choice), implemented as a compact segmented control at the top of the expanded body.

Per-tool Preview shaping (the fields were confirmed with the user):

- **Closet Agent — `search_closet` call (request):** show only the necessary args — Description, Category, Colors (chips), Gender. Hide `source`, `user_id`, `shared_closet_id`, `limit`.
- **Closet Agent — `search_closet` result (response, the large one):** header "N items found" + a compact per-item summary showing a small thumbnail plus **Category, Colors, Tags, Season**. Deliberately **omit** `item_id`, `source`, `gender`, `attribution`, and the raw `image_url` text. (Confirmed: no gender field in the preview.)
- **styling_app — `style_synthesizer` call:** Style direction, Wearer (age + gender), Language, item count. Hide `user_id` and the raw item URLs.
- **styling_app — `style_synthesizer` result:** Model used, Language, Generation prompt. **Do not** repeat the item URLs or the coordinate URL text.
- **Final suggestion (final answer):** summary text only. **Do not** re-list the retrieved image data — the images are already presented in the candidate-selection and result areas.
- **Unknown / other tools:** fall back to the JSON view.

This is a **front-end-only, presentation** change. Every field the Preview needs already arrives inside `AgentEvent` (`seq`, `agentName`, `eventKind`, `toolName`, `toolArgs`, `toolResult`, `text`) — nothing changes in `fastapi-service` or `adk-agent-service`, no new endpoint, no data-model change. It builds directly on the MI redesign (`AgentEventTile` was themed there) and does not touch data flow or the four-tab identity.

How to see it working after the change: run a `SHARED_CLOSET` coordination, watch the accordion fill. Each step opens on the Preview by default (e.g. the Closet Agent step reads "8 items found" with small thumbnails + category/colors/tags/season, not a wall of JSON). Flip a tile to **Raw** and it shows the same event as indented JSON. Switch the UI to `English`/`日本語` and the Preview labels follow the current locale (the labels are chrome, not generated content).

This ExecPlan is authored at the user's explicit request and corresponds to feature-matrix milestone **MJ** (rows **MJ-1 … MJ-5**) and to `req-phase01.md` **§24** (Agent-Trace Preview/Raw Views), with supporting decision **ADL-037**.


## Progress


- [x] (2026-07-02) MJ-1 — `dart:convert` import added; `_TraceView` enum (`preview`/`raw`); `AgentEventTile` converted to `StatefulWidget` holding per-item `_view` state; compact `SegmentedButton<_TraceView>` at the top of the expanded body; Real JSON Raw view via `AgentEvent.toJson()` + `JsonEncoder.withIndent('  ')` (replaces the old Dart-map `detailText` dump; `detailText` now delegates to `toJson()` for backward-compat).
- [x] (2026-07-02) MJ-2 — `_SearchClosetPreview`: request shows Description/Category/Colors/Gender (hiding `source`/`user_id`/`shared_closet_id`/`limit`); response shows "N items found" header + `_ClosetItemRow` (48×48 thumbnail + Category/Colors/Tags/Season chips; no `item_id`/`source`/`gender`/`attribution`/raw URL text).
- [x] (2026-07-02) MJ-3 — `_StyleSynthesizerPreview`: call shows Style direction / Wearer (age+gender) / Language / item count; result shows Model / Language / Generation prompt (no item or coordinate image URLs).
- [x] (2026-07-02) MJ-4 — `_FinalAnswerPreview`: renders `event.text` as prose; unknown/empty events fall back to JSON so Preview is never empty. `_AgentPreview` dispatcher (routes by `toolName`/`eventKind`, JSON fallback for unrecognized events). Shared helper widgets: `_PreviewField` (88 px label + `Expanded` child), `_ChipRow` (compact `RawChip` wrap), `_ClosetItemRow`.
- [x] (2026-07-02) MJ-5 — ARB keys added to `app_en.arb` / `app_ja.arb` (`tracePreview`, `traceRaw`, `traceDescription`, `traceStyleDirection`, `traceWearer`, `traceItemCount`, `traceModelUsed`, `traceGenerationPrompt`, `traceTags`, `traceItemsFound`, `traceTargetAgent`); `flutter gen-l10n` regenerated. Test updated (`detailText` → `toJson()`). `flutter analyze` → No issues found; `flutter test` → **15 passed**. Two-language browser check passed. Post-check fix: added `transfer_to_agent` Preview to `_AgentPreview` dispatcher — shows `toolArgs['agent_name']` as a single labeled field ("Agent" / "エージェント") instead of falling back to JSON.


## Surprises & Discoveries


- Observation: the accordion already receives every field the Preview needs; this is purely a rendering change.
  Evidence: `flutter-web-app/lib/coordination/coordination_screen.dart:724-753` (`AgentEvent` carries `toolArgs`/`toolResult`/`text`), and `:755-766` (`detailText`) is the only place that renders them — as a Dart-map string join, not JSON. No SSE/contract change is required.


## Decision Log


- Decision: Make the Preview/Raw choice **per accordion item** (each tile owns its mode), defaulting to **Preview**.
  Rationale: Different steps warrant different scrutiny — a user skims Previews but a developer may want Raw on exactly one step. A single global toggle would force an all-or-nothing view. Per-tile state is cheap (`StatefulWidget` on `AgentEventTile`) and matches the accordion's item granularity.
  Date/Author: 2026-07-02 / ExecPlan

- Decision: Implement Preview as a set of **per-tool formatters** keyed on `toolName` + `eventKind`, with the JSON view as the universal fallback.
  Rationale: The three tools (`search_closet`, `style_synthesizer`, final answer) have distinct, known shapes; a small switch keeps each rendering explicit and readable, and any unrecognized event still degrades gracefully to Raw JSON rather than crashing or hiding data.
  Date/Author: 2026-07-02 / ExecPlan

- Decision: The Closet Agent response Preview shows **Category, Colors, Tags, Season** (+ a small thumbnail) and omits `item_id`, `source`, `gender`, `attribution`, and the raw `image_url` text.
  Rationale: These are the human-meaningful "why did this item match" signals. IDs/URLs are machine noise reachable via Raw; `source`/`attribution` are constant for a given run and shown elsewhere (the result panel carries the CC BY-SA attribution footer). Gender was explicitly dropped by the user.
  Date/Author: 2026-07-02 / ExecPlan

- Decision: The final-suggestion Preview does **not** re-list retrieved image data.
  Rationale: The candidate images already render in the candidate-selection area and the chosen coordinate in the result panel (`_CandidatePanel` / `_ResultPanel`). Repeating them in the trace is redundant and heavy. The user called this out explicitly.
  Date/Author: 2026-07-02 / ExecPlan

- Decision: This is front-end only; no backend/agent change, no new ExecPlan-tracked ADL beyond ADL-037, and `docs/architecture-overview.md` needs no update.
  Rationale: The change renders data already present in `AgentEvent`. It adds no component, port/adapter, data store, or endpoint, and moves nothing across the implemented ↔ planned boundary — the same reasoning MI used for the redesign.
  Date/Author: 2026-07-02 / ExecPlan


## Outcomes & Retrospective


**Completed 2026-07-02.** All MJ-1…MJ-5 milestones implemented and verified. `flutter analyze` clean; `flutter test` 15 passed; two-language (日本語/English) browser check passed against `make dev`.

Per-tool Preview summary:
- **`search_closet` call** — Description / Category / Colors (chips) / Gender; `source`/`user_id`/`shared_closet_id`/`limit` hidden.
- **`search_closet` result** — "N items found" + per-item 48×48 thumbnail + Category / Colors (chips) / Tags (chips) / Season; no IDs/URLs/gender/attribution.
- **`style_synthesizer` call** — Style / Wearer (age+gender) / Language / item count.
- **`style_synthesizer` result** — Model / Language / Generation prompt; no image URLs.
- **`transfer_to_agent`** — target agent name as a single labeled field (post-check fix; was falling back to JSON).
- **`final_answer`** — summary prose only; no retrieved image data re-listed.
- **Unknown events** — Raw JSON fallback (Preview never empty).


## Context and Orientation


All work is in `flutter-web-app/lib/coordination/coordination_screen.dart` plus the ARB catalogs. Relevant current state:

- `AgentEventTile` (`coordination_screen.dart:537-572`) is a `StatelessWidget`. It is an `ExpansionTile` whose single child is `SelectableText(event.detailText)` on a `surfaceContainerHighest` panel. The tile title comes from `event.summary(l10n)` (already localized for `search_closet` / `style_synthesizer`, `:768-783`).
- `AgentEvent` (`:724-753`) holds `seq`, `agentName`, `eventKind` (`tool_call` / `tool_result` / `final_answer` / `thinking` / …), `toolName`, `toolArgs`, `toolResult`, `text`.
- `AgentEvent.detailText` (`:755-766`) is the current developer dump: `parts.join('\n')` of `seq/agent/kind/tool/text/args/result`, where `args`/`result` are Dart-map `toString()`s (not JSON). This is what MJ-1 replaces with pretty JSON and MJ-2/3/4 supersede with Previews.

Known data shapes the Preview formatters target (from the ADK tools, confirmed by reading them):

- `search_closet` (`adk-agent-service/styling_app/tools/search_closet.py`): **args** `description, source, user_id, shared_closet_id, category, colors, gender, limit`; **result** is a list of `{item_id, source, image_url, category, tags, colors, season, gender, attribution}`. In the event stream the result list is under `toolResult['result']` (see `summary()`'s `toolResult?['result']` handling at `:770`).
- `style_synthesizer` (`adk-agent-service/styling_app/tools/style_synthesizer.py`): **args** `user_id, item_image_urls, style_description, gender, wearer_age, language`; **result** `{coordinate_image_url, items, model_used, generation_prompt, language}`.
- Final answer: `eventKind == 'final_answer'` with the natural-language text in `event.text`.

The candidate images and the final coordinate image are rendered by `_CandidatePanel` / `_CandidateCard` (`:574-675`) and `_ResultPanel` (`:677-722`) respectively — this is why the final-suggestion Preview must not duplicate image data.

Design/theme: the accordion is already themed by MI (Claude Design). New controls (the segmented toggle, chips, field labels) must consume the existing `ThemeData` and the reusable widgets in `flutter-web-app/lib/theme/components.dart` (`EyebrowLabel` for field captions where appropriate). Localization uses the MI-established `gen-l10n` catalogs (`lib/l10n/app_ja.arb` default / `app_en.arb`).


## Plan of Work


One internal effort, sequenced so the toggle/JSON infrastructure lands first, then each formatter.

### MJ-1 — Toggle + Raw JSON

1. Convert `AgentEventTile` to a `StatefulWidget` holding `_TraceView _view` (default `_TraceView.preview`).
2. In the expanded body, add a compact `SegmentedButton<_TraceView>` (or equivalent styled toggle) with **Preview** / **Raw** segments, consuming the theme. Below it, render the selected view.
3. Add a real JSON view: `AgentEvent.toJson()` returning an ordered `Map` (`seq, agentName, eventKind, toolName, toolArgs, toolResult, text`, omitting nulls), rendered via `const JsonEncoder.withIndent('  ')` inside a monospace `SelectableText` (the existing surface panel). Keep `detailText` only if still referenced by tests; otherwise remove it once superseded.

### MJ-2 — Closet Agent Preview

4. Add `_SearchClosetPreview` handling both `eventKind`s of `toolName == 'search_closet'`:
   - **call:** labeled rows for Description, Category, Colors (chips), Gender; skip `source`/`user_id`/`shared_closet_id`/`limit`.
   - **result:** a header "N items found" (localized, count-aware) + a wrap/list of compact item rows, each a small thumbnail (`image_url`) + Category, Colors (chips), Tags (chips), Season. No IDs/URLs/gender/attribution.

### MJ-3 — styling_app Preview

5. Add `_StyleSynthesizerPreview` for `toolName == 'style_synthesizer'`:
   - **call:** Style direction (`style_description`), Wearer (`wearer_age` + `gender`), Language, item count (`item_image_urls.length`).
   - **result:** Model used (`model_used`), Language, Generation prompt (`generation_prompt`). No item/coordinate URLs.

### MJ-4 — Final-suggestion Preview

6. Add a final-answer Preview (`eventKind == 'final_answer'`): render `event.text` as readable prose; do not re-list retrieved image data. For any event that matches no formatter, fall back to the Raw JSON view inside the Preview segment too (so Preview is never empty).

### MJ-5 — Localize + verify

7. Add ARB keys to `app_en.arb` / `app_ja.arb` for: Preview / Raw segment labels; field captions (Description, Category, Colors, Gender, Tags, Season, Style, Wearer, Language, Items, Model, Prompt); and the count-aware "N items found". Wire them through `AppLocalizations`.
8. Run `flutter gen-l10n`, `flutter analyze`, `flutter test`; do a two-language browser check of an expanded accordion in both Preview and Raw.


## Concrete Steps


Working directory: `/Users/ran/my-app/gen-fashion/flutter-web-app`.

Step 1 — Edit `lib/coordination/coordination_screen.dart`: make `AgentEventTile` stateful; add the `SegmentedButton` toggle; add `AgentEvent.toJson()` + the indented-JSON Raw view.

Step 2 — Add the per-tool Preview widgets (`_SearchClosetPreview`, `_StyleSynthesizerPreview`, final-answer preview) and a dispatcher keyed on `toolName`/`eventKind` with a JSON fallback.

Step 3 — Add ARB keys to `lib/l10n/app_en.arb` and `lib/l10n/app_ja.arb`; regenerate:

    flutter gen-l10n

Step 4 — Verify:

    flutter analyze          # expect: No issues found
    flutter test             # expect: green (update any test asserting the old detailText dump)

Step 5 — Manual browser check against `make dev` (repo root): run a `SHARED_CLOSET` coordination; confirm each tile opens on Preview (Closet step = "N items found" + thumbnails + category/colors/tags/season; styling step = style/wearer/language/model/prompt; final = prose only), flip a tile to Raw (indented JSON), and confirm labels follow `日本語`/`English`. Capture one screenshot per language for the Outcomes section.


## Validation and Acceptance


- Each accordion item defaults to **Preview** and can be switched to **Raw** independently; the choice persists while the tile stays mounted.
- **Raw** shows the event as indented, valid JSON (not a Dart-map dump).
- **Closet Agent** Preview: request shows only Description/Category/Colors/Gender; response shows "N items found" + per-item thumbnail + Category/Colors/Tags/Season, with no IDs, URLs, gender, or attribution text.
- **styling_app** Preview: call shows Style/Wearer/Language/item count; result shows Model/Language/Prompt; no item or coordinate URLs are dumped.
- **Final suggestion** Preview: summary prose only; retrieved image data is not re-listed.
- Preview labels are localized and follow the live UI language; generated content is unaffected.
- `flutter analyze` clean; `flutter test` green; two-language browser check passes.


## Idempotence and Recovery


All changes are additive and front-end only. If a Preview formatter encounters an unexpected shape it falls back to the Raw JSON view, so no event can render empty or crash the tile. No backend, contract, data-model, or Firestore change is involved, so there is nothing to migrate or roll back beyond reverting the edited Dart/ARB files. Re-run `flutter gen-l10n` if the generated localization file is stale.


## Artifacts and Notes


Files expected to change:

    flutter-web-app/lib/coordination/coordination_screen.dart   (stateful tile, toggle, JSON view, per-tool Preview widgets)
    flutter-web-app/lib/l10n/app_en.arb                          (Preview/Raw + field-label keys)
    flutter-web-app/lib/l10n/app_ja.arb                          (Preview/Raw + field-label keys)
    flutter-web-app/lib/l10n/app_localizations*.dart             (regenerated by flutter gen-l10n)

No changes in `fastapi-service/` or `adk-agent-service/`. Design reference: `temp-ui/flutter_ui_design_spec.md` (theme is already applied via MI).


## Interfaces and Dependencies


| Name | Location | Purpose |
|---|---|---|
| `AgentEventTile` (stateful) | `flutter-web-app/lib/coordination/coordination_screen.dart` | Hosts the per-item Preview⇄Raw toggle and dispatches to the right renderer |
| `AgentEvent.toJson()` | same file | Ordered map feeding the indented-JSON Raw view |
| `_SearchClosetPreview` / `_StyleSynthesizerPreview` / final-answer preview | same file | Per-tool user-friendly renderings keyed on `toolName`/`eventKind` |
| `AppLocalizations` / ARB catalogs | `flutter-web-app/lib/l10n/*.arb` → generated | Localized Preview/Raw + field labels (`ja`/`en`), per MI's i18n |
| `ThemeData` + `lib/theme/components.dart` | `flutter-web-app/lib/theme/` | Claude Design styling for the toggle, chips, and field captions (from MI) |
