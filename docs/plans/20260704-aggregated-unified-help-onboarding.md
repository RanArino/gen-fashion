# MM/MN — Unified Help, Closet/Coordination Onboarding, Touch Fixes & New-User Nudge

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.

## Purpose / Big Picture

Initially (Milestone MM), the goal was to address UI polish around onboarding and contextual help: the Closet page incorrectly showed a CC BY-SA 4.0 dataset banner, the Closet had no in-app explanation for first-time users, and Coordination mode/source segments lacked tooltips. Following that initial work, further refinements (Milestone MN) were identified based on user feedback: touch parity for hover-only tooltips, a truncated Japanese label in the language switcher, unifying multiple help dialogs into a single global accordion dialog, and adding an animation to nudge new users to view the help.

After the combined changes: 
1. The CC BY-SA banner is removed from the Closet page and Coordination result panel, remaining only on the Shared tab (`shared_closet_gallery.dart`) where the dataset is actually used.
2. One unified `showAppHelpDialog` (`lib/shared/help_dialog.dart`) triggered by the global header Information icon contains an Accordion with four `ExpansionTile` sections (Closet/Coordinate/History/Shared), auto-expanding the section for whichever page the user opened it from.
3. The Shared section's copy explicitly states the shared closet exists so users can try a full styling demo without uploading their own clothes first.
4. Coordination's source selector and Closet's ownership filter each gained an always-visible caption for touch users, while retaining hover/long-press tooltips as a desktop bonus. Mode/source segmented buttons in Coordination and Closet also show tooltips.
5. The header language switcher no longer force-truncates the "日本語" label.
6. The header info icon pulses when the closet is empty or the account was created in the last 24h, stopping for the rest of the session once tapped. 

All changes are front-end + localization only — no backend/data-model change.

## Progress

**Milestone MM:**
- [x] (2026-07-04) MM-1 — Removed `AttributionFooter()` from both `ClosetScreen` build branches (`closet_screen.dart`), collapsing the now-redundant one-child `Column` wrappers to `_buildBody()` directly. Also removed the conditional `AttributionFooter()` from `_ResultPanel` (`coordination_screen.dart:1769-1772`) and its now-unused `source` field/parameter.
- [x] (2026-07-04) MM-2 — Added `showClosetHelpDialog` and `_ClosetHelpButton` in `closet_screen.dart` (Note: later replaced in MN-2).
- [x] (2026-07-04) MM-3 — Added `tooltip:` to all four `ButtonSegment`s in `coordination_screen.dart`'s `_Controls` (mode: `STANDARD`/`ASSISTED` reusing `modeStandardHint`/`modeAssistedHint`; source: `SHARED_CLOSET`/`CLOSET` using new `sourceSharedHint`/`sourceMineHint`).
- [x] (2026-07-04) MM-4 — Added `tooltip:` to `ClosetFilterBar`'s `owned`/`interesting` `ButtonSegment`s, and a live-updating caption `Text` under the Ownership dropdown in `_onEdit`.
- [x] (2026-07-04) MM-5 — Added 9 new ARB keys to both `app_en.arb` and `app_ja.arb`; ran `flutter gen-l10n`, `flutter analyze` (clean), `flutter test` (43 passed).
- [x] (2026-07-04) MM-6 — Added `docs/req-phase02.md` §4 and this `MM` milestone to `docs/feature-matrix-phase02.md`.

**Milestone MN:**
- [x] (2026-07-04) MN-1 — Added `lib/shared/help_dialog.dart` with `showAppHelpDialog(context, {required initialSection})`, four `ExpansionTile` sections. Retired `showSharedClosetAboutDialog` from `attribution.dart`; `AttributionFooter.onTap` now calls `showAppHelpDialog(..., initialSection: helpSectionShared)`.
- [x] (2026-07-04) MN-2 — Removed `_ClosetHelpButton`/`showClosetHelpDialog` from `closet_screen.dart`. `home_screen.dart`'s global info `IconButton` now maps the active tab index to a section id and opens the unified dialog.
- [x] (2026-07-04) MN-3 — Added an always-visible caption below Coordination's source `SegmentedButton` and below Closet's ownership `SegmentedButton` in `ClosetFilterBar`, reusing existing hint keys. Existing hover `tooltip:` attributes kept as-is.
- [x] (2026-07-04) MN-4 — Replaced `_LanguageSwitcher`'s `Chip`-wrapped label with a plain icon+text `Row` inside the same `PopupMenuButton`.
- [x] (2026-07-04) MN-5 — `_HomeScreenState` gained `SingleTickerProviderStateMixin` + an `AnimationController` driving a `ScaleTransition` around the header info icon, animating when `users/{uid}/closet.limit(1)` shows empty or `users/{uid}.createdAt` is within 24h. A session-only `_helpNudgeDismissed` bool stops it for the session.
- [x] (2026-07-04) MN-6 — Added `appHelpTooltip`, `appHelpTitle`, `helpCoordinateIntro`, `helpHistoryBody`, `emptyClosetHelpHint` to both ARB catalogs; reworded `sharedAboutBody`; removed now-unused ARB keys. Ran checks (`flutter test` 43/43).

## Surprises & Discoveries

- Observation: `AttributionFooter` had a fourth call site inside `_ResultPanel` (`coordination_screen.dart:1767`). Initially left untouched, but removed after user review of a live screenshot.
- Observation: `ClosetScreen`'s `embedded: false` branch (own `Scaffold`+`AppBar`) is never instantiated in the running app, but was edited symmetrically.
- Observation: Removing `AttributionFooter()` from the `Column`s left each with a single child. Using `_buildBody()` directly instead of wrapping it in an `Expanded` worked since it sizes itself correctly.
- Observation: `Chip`'s internal `DefaultTextStyle` hard-codes `overflow: TextOverflow.fade, maxLines: 1, softWrap: false`. This caused the Japanese label truncation, not insufficient AppBar space. Fixed by dropping `Chip` entirely.
- Observation: No touch-vs-mouse detection, "new user" flag, or animation infrastructure existed in `lib/` prior to this change. Web-only target meant Flutter's `Tooltip` long-press-on-touch behavior wasn't discoverable. Fixed by adding always-visible captions.
- Observation: `ClosetScreen`'s existing `_stream()` was a good precedent for a cheap `.limit(1)` existence check in `HomeScreen`.
- Observation: No test in `test/` referenced the removed dialogs or ARB keys, so `flutter test` stayed at 43/43 without test updates.

## Decision Log

- Decision: Colocate `showClosetHelpDialog` and `_ClosetHelpButton` in `closet_screen.dart`. (Later superseded by MN: unified into `help_dialog.dart`).
- Decision: Remove `_ResultPanel`'s conditional `AttributionFooter()` (`coordination_screen.dart:1769-1772`). 
  Rationale: The user reviewed a live screenshot of the Coordinate result panel and judged the banner unnecessary there too.
  Date/Author: 2026-07-04 / User
- Decision: No new ADL / `docs/architecture-overview.md` update; add a new terse `req-phase02.md` §4 instead.
  Rationale: Pure front-end UI change with no new architecture component.
  Date/Author: 2026-07-04 / ExecPlan
- Decision: Reuse existing ARB keys wherever an equivalent string already exists, and share hint keys between tooltip and edit-dialog caption to avoid key sprawl.
  Date/Author: 2026-07-04 / ExecPlan
- Decision: New-user signal = closet-empty OR account created within the last 24h (reusing `createdAt` field).
  Rationale: User explicitly named both conditions. Ensures a user who uploads one item immediately won't stop being nudged before exploring other tabs.
  Date/Author: 2026-07-04 / User, ExecPlan
- Decision: Nudge dismissal is session-only (in-memory `bool`).
  Rationale: Recommended option chosen by the user to avoid an extra write/dependency for a minor UX nicety.
  Date/Author: 2026-07-04 / User
- Decision: Retire `showSharedClosetAboutDialog` entirely rather than keep it alongside the new unified dialog.
  Rationale: The user asked to fold the Closet-only icon into the existing header icon, implying one dialog to avoid duplicated CC BY-SA content.
  Date/Author: 2026-07-04 / ExecPlan

## Outcomes & Retrospective

**Completed 2026-07-04.** `flutter analyze` reports "No issues found!"; `flutter test` reports 43/43 passing.

Manual verification used a `flutter build web --release` bundle served via `python3 -m http.server`, built with `E2E_AUTO_SIGN_IN=true` against the Docker stack, and driven by a Playwright script. 

Confirmed via screenshots and live session:
- Closet page: the CC BY-SA banner is gone.
- The item-edit dialog's Ownership caption switches live the instant the dropdown is changed.
- Hovering segments (Coordination mode/source, Closet ownership) shows tooltips.
- The header info icon opens one dialog titled "このアプリの使い方"/"How this app works" with four Accordion sections, auto-expanding the active tab's section.
- The Shared section shows the reworded demo-purpose copy and the CC BY-SA dataset info/link.
- Coordination's source caption and Closet's ownership caption render without hovering, confirming touch parity.
- The language switcher shows the full "日本語" and "English" labels — no truncation.
- Shared tab still shows the CC BY-SA banner unchanged; Coordinate result panel no longer shows it under any source.

**Known verification gap:** The header icon's pulsing-nudge animation and the empty-closet help button state were reviewed in code but not observed live. This is because the local emulator test account already has closet items and was created >24h before this session. Reproducing an empty/new-account state required seeding a fresh emulator user, which was judged out of scope for this pass.

## Context and Orientation

- **`flutter-web-app/lib/home/home_screen.dart`**: Shares single `GlassAppBar`; owns `_index`, the header info icon, `_LanguageSwitcher`, and the nudge `AnimationController` + two Firestore watchers (`_closetStream`, `_userDocFuture`).
- **`flutter-web-app/lib/shared/help_dialog.dart`** (new): `showAppHelpDialog` + section constants used by `home_screen.dart` and `attribution.dart`.
- **`flutter-web-app/lib/shared/attribution.dart`**: Now only contains `AttributionFooter` (Shared-tab banner widget).
- **`flutter-web-app/lib/closet/closet_screen.dart`**: `ClosetFilterBar` (ownership caption added), `_EmptyState` (hint text added), `_onEdit` (live caption added).
- **`flutter-web-app/lib/coordination/coordination_screen.dart`**: `_Controls`'s source `SegmentedButton` uses touch-friendly caption and tooltips.
- **`flutter-web-app/lib/auth/auth_service.dart:49`**: `createdAt` field read by the new nudge logic.
- **ARB catalogs**: `app_en.arb` and `app_ja.arb` updated with unified help keys, hint keys, and removed unused keys.
- **Tracking**: `docs/feature-matrix-phase02.md` milestones MG, MK, ML precede MM/MN; `docs/req-phase02.md` gained a new §4.

## Plan of Work

See Progress above for the structured breakdown of the original MM and MN milestone tasks.

## Concrete Steps

Already executed — see Progress. Commands used during verification:

    flutter gen-l10n
    flutter analyze          # actual: No issues found!
    flutter test             # actual: 43/43 passed

## Validation and Acceptance

- Automated checks: `flutter analyze` clean; `flutter test` 43/43 green.
- Manual two-language browser check covering accordion auto-expand per tab, Shared section content/link, touch-safe captions, language-switcher label, and CC BY-SA banner removal. Code-level review for the nudge animation.

## Idempotence and Recovery

All changes are plain Dart widget/function edits, ARB additions, and doc-file updates. No migrations, no data writes, no server/API changes. Re-running `flutter gen-l10n`/`flutter analyze`/`flutter test` is side-effect-free.

## Artifacts and Notes

Files modified/added across both plans:
    flutter-web-app/lib/home/home_screen.dart
    flutter-web-app/lib/closet/closet_screen.dart
    flutter-web-app/lib/coordination/coordination_screen.dart
    flutter-web-app/lib/shared/help_dialog.dart
    flutter-web-app/lib/shared/attribution.dart
    flutter-web-app/lib/l10n/app_en.arb
    flutter-web-app/lib/l10n/app_ja.arb
    flutter-web-app/lib/l10n/app_localizations*.dart
    docs/req-phase02.md
    docs/feature-matrix-phase02.md

Verification used `flutter build web --release` dart-defines matching `Makefile`'s `web` target plus `E2E_AUTO_SIGN_IN=true`. 
Playwright driver: globally-installed `playwright` npm package.

## Interfaces and Dependencies

| Symbol | Location | Change |
|---|---|---|
| `showAppHelpDialog` | `lib/shared/help_dialog.dart` | New unified entry point, replaces `showSharedClosetAboutDialog` and `showClosetHelpDialog`. |
| `AttributionFooter` | `lib/shared/attribution.dart` | `onTap` repointed to `showAppHelpDialog`; calls removed from Closet/Coordinate. |
| `_HelpIconButton` | `lib/home/home_screen.dart` | Wraps the header info `IconButton` with the nudge `ScaleTransition`. |
| `_LanguageSwitcher` | `lib/home/home_screen.dart` | `Chip` replaced with a plain `Row`. |
| `ButtonSegment.tooltip` | `package:flutter/material.dart` | Built-in segment tooltip used. |
| `ItemOwnership` enum | `lib/closet/closet_item.dart` | Drives ownership hint text in filter-chip tooltip and edit-dialog caption. |
