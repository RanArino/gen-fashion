# MI — Language Settings (JP/EN) & UI/UX Redesign (Claude Design)


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


This ExecPlan covers two user-facing goals for the Flutter Web client (`flutter-web-app/`), authored together because both are front-end polish work that touches the same screens:

1. **Configurable language (Japanese / English).** Today the UI chrome is a hard-coded mix of Japanese labels (`共有クローゼットについて`) and English labels (`Closet`, `Coordinate`), and agent-generated content (coordinate reasoning, item descriptions, final answer) comes back in whatever language the model happens to choose. After this change the user picks a language (`日本語` / `English`) from an in-app switcher; **the whole UI chrome re-renders immediately** in that language, and **new** coordination runs generate their natural-language content in the selected language. The selection is remembered per user (`users/{uid}.language`).

2. **UI/UX redesign using the Claude Design system.** The app currently uses a default Material 3 indigo `ColorScheme.fromSeed` theme with stock widgets. After this change the app adopts the earthy, editorial design system captured in `temp-ui/` (`flutter_ui_design_spec.md` + the `Gen-Fashion.dc.html` mock): warm-beige scaffold, off-white cards, terracotta accent, and the three-font typographic system (`Archivo` body, `Instrument Serif` display, `Space Mono` eyebrow labels). The four-tab structure (Closet / Coordinate / History / Shared) is unchanged; only presentation changes.

**Explicit non-goal — no retroactive translation of past data (deliberate, to avoid needless system load).** Historical sessions keep the language they were generated in. A coordinate whose reasoning was generated in Japanese still displays in Japanese in the History gallery even after the user switches the UI to English. Language applies **at processing time** and is **frozen at generation time** in each session's stored `styleResult` / `userPreference.language`. Only the app chrome (buttons, tab labels, form labels, static copy) follows the live language selection.

How to see it working after the change: sign in, open the language switcher and choose `English` — every tab label, button, and form field flips to English instantly. Run a `SHARED_CLOSET` coordination; the agent trace summaries and the final coordinate description come back in English. Switch back to `日本語` and open History — the English run you just made still reads in English (not retranslated), while a new run reads in Japanese. Throughout, the app wears the Claude Design look (beige canvas, serif headers, mono eyebrow labels, terracotta primary buttons).

This ExecPlan is authored at the user's explicit request. It corresponds to feature-matrix milestone **MI** (rows **MI-1 … MI-7**) and to `req-phase01.md` **§22** (Localization) and **§23** (UI/UX Redesign), with supporting decisions **ADL-035** (i18n) and **ADL-036** (design system).


## Progress


- [x] (2026-07-02 JST) Milestone A — Localization foundation: `flutter_localizations` + `gen-l10n` (ARB `ja`/`en`), `LocaleController`/`LocaleScope` wired into `MaterialApp`, a header language switcher, and per-user persistence to `users/{uid}.language`. Verified with `flutter analyze` and `flutter test`.
- [x] (2026-07-02 JST) Milestone B — Localized generated content: `UserPreference.language` in the domain, Flutter sends `userPreference.language` at run start, `adk-agent-service` injects language into run context/tool args, `style_synthesizer` includes it in the prompt/result, and History/result rendering remains verbatim. Verified with ADK pytest.
- [x] (2026-07-02 JST) Milestone C — Design system theme: central `lib/theme/app_theme.dart` and `lib/theme/components.dart` implement the `temp-ui` palette/typography/components and are wired into `MaterialApp.theme`.
- [x] (2026-07-02 JST) Milestone D implementation — Login, Home shell/nav, Closet, Coordinate, History, Shared gallery, attribution, dialogs, snackbars, and test wrappers were localized/restyled with the theme/components. Automated verification passed; manual browser screenshots/checks remain to be captured.


## Surprises & Discoveries


- Observation: `userPreference` already flows end-to-end as an opaque `dict` from Flutter through FastAPI to `adk-agent-service`.
  Evidence: `flutter-web-app/lib/coordination/coordination_screen.dart:78-84` builds the `userPreference` map (including `gender`), `fastapi-service/app/adapters/adk_agent_run.py:27` forwards `"userPreference": request.user_preference`, and `adk-agent-service/styling_app/server.py:34` receives it. This means `language` rides the existing transport with no new request field — only producers/consumers of the value change. Mirror the `gender` plumbing exactly.

- Observation: FastAPI's local `.venv` exists but does not include `pytest`, so the FastAPI suite could not be run without modifying the environment.
  Evidence: from `fastapi-service`, `./.venv/bin/python -m pytest -q` exits with `No module named pytest`. The touched FastAPI file was still checked with `./.venv/bin/python -m py_compile app/domain/styling/value_objects.py`.


## Decision Log


- Decision: Implement UI localization with Flutter's official `flutter_localizations` + `gen-l10n` (ARB files), default locale `ja`, supported `[ja, en]`.
  Rationale: This is the first-party Flutter i18n path (no third-party runtime), integrates directly with `MaterialApp.localizationsDelegates` / `supportedLocales`, and produces a typed `AppLocalizations` accessor. The audience is Japan-primary and existing user-facing strings/errors are already Japanese, so `ja` is the sensible default; `en` is the added option.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Persist the user's language in two places with distinct meaning — `users/{uid}.language` (the live per-user chrome preference) and `sessions/{id}.userPreference.language` (the value frozen at generation time).
  Rationale: The chrome preference must survive reloads and follow the user, so it lives on the user document (read on login, written by the switcher). The generation-time value must be immutable per session so History can render each past run in the language it was produced in. Storing it inside the existing `userPreference` map mirrors `gender` and requires no new session field.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Localize agent-**generated** natural-language content at generation time and never retranslate it.
  Rationale: The user's requirement is explicit: "applied at processing time; past data is not automatically translated (it remains in the language selected at generation to avoid unnecessary system load)." Retroactive translation would add model calls and cost for no product value. The app instructs the orchestrator/`style_synthesizer` to author reasoning/descriptions/final-answer in `language`; the History and result panels render the stored text verbatim regardless of the current UI locale.
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Apply the `temp-ui` Claude Design system through a single central `theme.dart` (`ThemeData` + `google_fonts`), not by hand-styling each widget.
  Rationale: `temp-ui/flutter_ui_design_spec.md` already maps the design tokens to `ThemeData`/`google_fonts`. A central theme keeps the change surgical (screens consume the theme), matches the repo's preference for boring/explicit solutions, and keeps future screens on-brand automatically. A small set of reusable widgets covers the few patterns Material lacks (mono eyebrow label, glass header, terracotta pill button).
  Date/Author: 2026-07-01 / ExecPlan

- Decision: Keep the existing four-tab structure and screen composition; change presentation only. Do not introduce routing here.
  Rationale: The redesign is a visual refresh, not an information-architecture change. URL routing / browser back-button support is a separate tracked milestone (**MG**, `req-phase01.md` §20) and must not be entangled with this work per "one ExecPlan at a time."
  Date/Author: 2026-07-01 / ExecPlan

- Decision: `docs/architecture-overview.md` does not need updating.
  Rationale: This change adds a `language` field to the existing `UserPreference` value object and the existing `userPreference` transport (mirroring `gender`), and restyles the Flutter presentation layer. It adds no new component, port/adapter, data store, or external service, and moves nothing across the implemented ↔ planned boundary. (No new HTTP endpoint is added — unlike ME, which is why ME updated the overview and this does not.)
  Date/Author: 2026-07-01 / ExecPlan

- Decision: No new environment variable is introduced for the default language.
  Rationale: Language is a per-user client preference persisted in Firestore, not a deployment setting. The default (`ja`) is a client constant. Adding an env var would be speculative configurability the requirement does not need.
  Date/Author: 2026-07-01 / ExecPlan


## Outcomes & Retrospective


Implementation landed for the code milestones. Static Flutter chrome across Login, Home/nav, Closet, Coordinate, History, Shared gallery, attribution dialog/footer, snackbars, and edit/delete dialogs is externalized into `app_en.arb` / `app_ja.arb`; generated content language is frozen by sending `userPreference.language` at run start and passing it through ADK tool args to `style_synthesizer`.

Verification completed:

    cd flutter-web-app && flutter analyze
    No issues found

    cd flutter-web-app && flutter test
    15 tests passed

    cd adk-agent-service && ./.venv/bin/pytest -q
    41 passed, 1 warning

    cd fastapi-service && ./.venv/bin/python -m py_compile app/domain/styling/value_objects.py
    # passed

Remaining verification: manual browser checks/screenshots in both languages and a real/emulated coordination run confirming persisted `users/{uid}.language` and `sessions/{id}.userPreference.language` in Firestore.


## Context and Orientation


The Flutter Web client lives in `flutter-web-app/`. Relevant current state:

- `flutter-web-app/lib/main.dart` builds `MaterialApp(title: 'gen-fashion', theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo), useMaterial3: true), home: const AuthGate())`. There are **no** `localizationsDelegates`, `supportedLocales`, or `locale` today, and no `l10n.yaml` / ARB files (`grep` for `flutter_localizations`/`AppLocalizations`/`intl` returns nothing).
- `flutter-web-app/lib/home/home_screen.dart` renders the `AppBar` (title `gen-fashion`, tooltips `共有クローゼットについて` / `Sign out`) and a `NavigationBar` with hard-coded English labels (`Closet`, `Coordinate`, `History`, `Shared`). It switches the four screens by `int _index`.
- `flutter-web-app/lib/coordination/coordination_screen.dart` holds the pre-run preference form. `String _gender = 'common'` (line 32) is sent in the `userPreference` map (lines 78-84) via `ApiClient.selectSource(...)`. This is the exact pattern `language` must follow. The screen also renders the agent-event accordion, candidate cards, and the result image.
- `flutter-web-app/lib/closet/closet_screen.dart`, `closet/shared_closet_gallery.dart`, `history/history_screen.dart`, `auth/login_screen.dart` contain the remaining user-facing strings and stock Material styling.
- `flutter-web-app/lib/config.dart` centralizes build-time config (`--dart-define`); `flutter-web-app/lib/auth/auth_service.dart` performs first-login `users/{uid}` bootstrap (the natural place to also read/default `language`).
- `flutter-web-app/pubspec.yaml` depends on `firebase_core`, `firebase_auth`, `cloud_firestore`, `http`, `fetch_client`, `image_picker`, `uuid`, `url_launcher`. There is **no** `google_fonts` and **no** `flutter_localizations` yet.

Backend / agent plumbing for the generated-content half:

- `fastapi-service/app/domain/styling/value_objects.py` defines `UserPreference` with `occasion / season / style / color_preference / gender` (frozen dataclass). `language` is added here.
- `fastapi-service/app/adapters/adk_agent_run.py:27` forwards the raw `userPreference` dict to `adk-agent-service`; no change needed for transport.
- `adk-agent-service/styling_app/server.py` reads `gender = request.user_preference.get("gender") or "common"` (lines 69, 172), builds the run context via `_message_context(...)` (line 341), and binds `style_synthesizer` (`_build_generate_style_tool`, line ~313). `language` is read the same way, injected into the context with an explicit "author all natural-language output in {language}" instruction, and passed into `style_synthesizer`.
- `adk-agent-service/styling_app/tools/style_synthesizer.py` composes the generation prompt (uses `gender`, `wearer_age`). It gains a `language` parameter used in the prompt/description.
- `sessions/{id}.userPreference` (Firestore, `req-phase01.md` §8.1) persists the map, so the generation-time `language` is already durable once it is part of the map. `history/history_item.dart` reads session/result fields for the History gallery.

Design source of truth: `temp-ui/flutter_ui_design_spec.md` (tokens + Flutter mapping) and `temp-ui/Gen-Fashion.dc.html` (the visual mock; same four tabs, plus a "Studio"/"Wardrobe" naming flourish that we treat as cosmetic — screen identity stays Closet/Coordinate/History/Shared). The mock has **no** language switcher, so the switcher is a new control designed to match the system (a `Space Mono` uppercase segmented control / menu in the header).


## Plan of Work


The work is four internal milestones. A and C are independent and can proceed in parallel; B depends on A (it reuses the `Locale` controller's current language code when starting a run); D depends on C (screens consume the theme) and benefits from A (localized strings) landing first.

### Milestone A — Localization foundation (MI-1)


Add first-party Flutter localization and a live language switcher.

1. Add dependencies to `flutter-web-app/pubspec.yaml`: `flutter_localizations` (from SDK) and `intl` (version pinned by the current Flutter SDK). Enable `flutter: generate: true`.
2. Add `flutter-web-app/l10n.yaml`:

       arb-dir: lib/l10n
       template-arb-file: app_en.arb
       output-localization-file: app_localizations.dart
       output-class: AppLocalizations

3. Create `flutter-web-app/lib/l10n/app_en.arb` and `app_ja.arb` with every user-facing string in the app. Seed the catalog from a grep of literal strings across `lib/` (nav labels, app-bar title/tooltips, buttons, form field labels/hints, dialog copy, snackbars, error text, attribution copy). Keys are semantic (e.g. `navCloset`, `signOut`, `sharedClosetAbout`, `preferenceGenderLabel`).
4. Introduce a `Locale` controller. The simplest sufficient approach: a `ValueNotifier<Locale>` (`LocaleController`) held above `MaterialApp`, exposed via a small `InheritedNotifier` (`LocaleScope`). `MaterialApp` reads `locale: controller.value`, sets `localizationsDelegates: [AppLocalizations.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate, GlobalCupertinoLocalizations.delegate]` and `supportedLocales: AppLocalizations.supportedLocales`. Default `Locale('ja')`.
5. Persist and restore the preference: on sign-in, read `users/{uid}.language` (in `auth_service.dart`'s bootstrap path, defaulting to `ja` and writing it on first login); set the controller from it. The switcher writes the new value to `users/{uid}.language` and updates the controller. Because chrome is driven by `MaterialApp.locale`, the whole tree re-renders on change.
6. Add the switcher UI to the Home app bar: a compact `日本語 / English` control styled later in Milestone D (functionally a `PopupMenuButton` or segmented toggle). Replace hard-coded nav/app-bar strings with `AppLocalizations.of(context)!.…`.

Acceptance: toggling the switcher flips all chrome strings live and survives reload (value read back from Firestore).

### Milestone B — Localized generated content, frozen at generation (MI-2, MI-3)


Thread `language` through to generation and persist it per session; render history in the stored language.

1. `fastapi-service/app/domain/styling/value_objects.py`: add `language: Optional[str] = None` to `UserPreference`.
2. Flutter `coordination_screen.dart`: include `'language': localeController.value.languageCode` in the `userPreference` map sent by `_start()` (alongside `gender`). This freezes the language chosen when the run starts.
3. `adk-agent-service/styling_app/server.py`: read `language = request.user_preference.get("language") or "ja"` in both the propose and generate paths (mirroring the two `gender` reads at lines 69/172). Inject an explicit instruction into `_message_context(...)` such as: "Author all natural-language output (reasoning, item descriptions, final answer) in {language_display}." Pass `language` into `_build_generate_style_tool(...)`.
4. `adk-agent-service/styling_app/tools/style_synthesizer.py`: add a `language: str = "ja"` parameter and include the language in the composed prompt/description so the generated coordinate text matches.
5. Persistence: because `userPreference` (with `language`) is already written to `sessions/{id}` and the generated reasoning/description is stored in `styleResult`, the generation-time language is durable with no schema change. Confirm the value is present on the persisted session document.
6. Flutter History/result rendering: ensure `history/history_screen.dart` and the coordination result panel render the **stored** reasoning/description text verbatim (they already display returned strings; verify no client-side re-localization is applied to generated content). The History gallery must not translate past runs when the UI language changes.

Acceptance: a run started while the UI is English produces English reasoning/description and persists it; switching the UI to Japanese and reopening History still shows that run in English; a fresh run shows Japanese.

### Milestone C — Design system theme (MI-4, MI-5)


1. Add `google_fonts` to `flutter-web-app/pubspec.yaml`.
2. Create `flutter-web-app/lib/theme/app_theme.dart` implementing `temp-ui/flutter_ui_design_spec.md`:
   - Palette constants: scaffold `#ECE8DF`, card `#FBF9F4`, secondary panel `#F6F3EC`, primary text `#1B1915`, muted `#8B8578`, tertiary `#514C42`, accent `#B0563C`, success `#6F7D5A`, error `#A2463A`, border `Color(0x1C1B1915)`-ish (dark @ ~0.11–0.16).
   - `ThemeData(useMaterial3: true, scaffoldBackgroundColor: 0xFFECE8DF, colorScheme: …)` with `Archivo` as the base text font (`GoogleFonts.archivoTextTheme`), plus explicit `TextStyle`s for `Instrument Serif` display/headers and a `Space Mono` eyebrow style (uppercase, `letterSpacing ≈ 0.2em`).
   - Component themes: `elevatedButtonTheme` (dark `#1B1915` / accent, radius 2), `outlinedButtonTheme` (transparent, hairline border), `cardTheme` (`#FBF9F4`, hairline border, radius 3), `inputDecorationTheme` (fill `#FBF9F4`/`#F6F3EC`, radius 2, accent focus border), `navigationBarTheme` (beige, accent indicator).
3. Create a small `flutter-web-app/lib/theme/components.dart` with reusable widgets the design needs beyond stock Material: `EyebrowLabel` (mono uppercase caption), `SectionCard`, `PrimaryActionButton` / `SecondaryActionButton` (pill vs. slight-radius per spec), and a `GlassAppBar` wrapper (`BackdropFilter` blur for the sticky header). Keep these minimal — only what the screens actually reuse.
4. Wire `theme:` into `MaterialApp` in `main.dart`, replacing `ColorScheme.fromSeed(seedColor: Colors.indigo)`.

Acceptance: the app renders with the beige canvas, serif headers, mono eyebrow labels, and terracotta buttons; `flutter analyze` is clean.

### Milestone D — Restyle screens, responsive, verification (MI-6, MI-7)


Apply the theme and components to each screen, using localized strings from Milestone A. Touch presentation only; do not change data flow or the four-tab identity.

1. `auth/login_screen.dart`: editorial hero with `Instrument Serif` title, mono eyebrow, terracotta sign-in button.
2. `home/home_screen.dart`: `GlassAppBar` with the styled language switcher + info/sign-out icon buttons; `NavigationBar` themed with accent indicator and localized labels.
3. `closet/closet_screen.dart` + `closet/shared_closet_gallery.dart`: `3/4` aspect cards, hairline borders, eyebrow metadata (category/colors/season/tags/gender), themed edit dialog and count chip.
4. `coordination/coordination_screen.dart`: themed preference form (inputs, gender + the new language display), a readable accordion trace (themed `ExpansionTile`/summary), candidate cards, and the result panel with `16/10` imagery.
5. `history/history_screen.dart`: `16/10` history cards with date/source/selected-garment metadata in the design system.
6. Responsiveness: constrain content width on wide screens, wrap/flow on narrow, ensure no overlapping text and ergonomic tap targets.
7. Verify (see Concrete Steps): `flutter analyze`, `flutter test`, and a manual browser check in both languages.

Acceptance: all five screens render in the Claude Design system, in both languages, responsively, with the existing flows intact.


## Concrete Steps


Working directory for Flutter: `/Users/ran/my-app/gen-fashion/flutter-web-app`. Working directory for backend/agent: `/Users/ran/my-app/gen-fashion`.

Step 1 — Milestone A deps and config:

    cd /Users/ran/my-app/gen-fashion/flutter-web-app
    # edit pubspec.yaml: add flutter_localizations (sdk), intl; set flutter.generate: true; add google_fonts
    flutter pub get

Step 2 — Add `l10n.yaml`, `lib/l10n/app_en.arb`, `lib/l10n/app_ja.arb`; run codegen:

    flutter gen-l10n
    # generates lib/l10n/app_localizations.dart (AppLocalizations)

Step 3 — Add `LocaleController` / `LocaleScope`, wire `MaterialApp` (`locale`, `localizationsDelegates`, `supportedLocales`) in `lib/main.dart`; read/write `users/{uid}.language` in `lib/auth/auth_service.dart`; add the switcher and replace chrome strings in `lib/home/home_screen.dart`.

Step 4 — Milestone B: edit `UserPreference` (`fastapi-service/app/domain/styling/value_objects.py`); add `'language'` to the `userPreference` map in `lib/coordination/coordination_screen.dart`; read+inject `language` in `adk-agent-service/styling_app/server.py`; add the `language` param to `adk-agent-service/styling_app/tools/style_synthesizer.py`.

Step 5 — Milestone C: create `lib/theme/app_theme.dart` and `lib/theme/components.dart`; wire `theme:` in `lib/main.dart`.

Step 6 — Milestone D: restyle Login, Home, Closet, Shared, Coordinate, History.

Step 7 — Verify Flutter:

    cd /Users/ran/my-app/gen-fashion/flutter-web-app
    flutter analyze          # expect: No issues found
    flutter test             # expect: existing widget/API tests pass (update snapshots/labels that reference old strings)

Step 8 — Verify backend/agent (only the two files changed there):

    cd /Users/ran/my-app/gen-fashion/fastapi-service
    .venv312/bin/pytest -q   # UserPreference change is additive; expect green
    cd /Users/ran/my-app/gen-fashion/adk-agent-service
    pytest -q                # style_synthesizer/server language plumbing; expect green (extend tool tests)

Step 9 — Manual browser check against `make dev` (from repo root): sign in, toggle `English`/`日本語` (chrome flips live and persists across reload), run a `SHARED_CLOSET` coordination in each language and confirm generated text language, then confirm History shows each past run in its generation-time language. Capture one screenshot per language and per redesigned screen for the Outcomes section.


## Validation and Acceptance


Localization (MI-1 / MI-2 / MI-3):

- Selecting `English` re-renders every chrome string (nav, app bar, buttons, form labels, dialogs, snackbars) in English immediately; selecting `日本語` reverts. The choice persists across a full reload (read back from `users/{uid}.language`).
- A coordination run started under `English` returns reasoning / item descriptions / final answer in English and persists them on the session; a run under `日本語` returns Japanese.
- After switching the UI to `日本語`, the previously-generated English run still displays in English in the History gallery and the result panel (no retranslation). This is the load-bearing "past data is not automatically translated" acceptance.
- `flutter analyze` clean; `flutter test` green; `fastapi-service` and `adk-agent-service` `pytest` green.

UI/UX redesign (MI-4 / MI-5 / MI-6 / MI-7):

- The app renders in the Claude Design system: beige `#ECE8DF` scaffold, off-white `#FBF9F4` cards with hairline borders, terracotta `#B0563C` primary actions, `Instrument Serif` headers, `Space Mono` uppercase eyebrow labels, `Archivo` body.
- All five screens (Login, Closet, Coordinate, History, Shared) are restyled with the existing flows intact and the four-tab identity unchanged.
- Layouts are responsive (content constrained on wide screens, no overlapping text, ergonomic tap targets) and correct in both languages.


## Idempotence and Recovery


All edits are additive and reversible. `UserPreference.language` is optional and defaults to `None`, so persisted sessions without it, and the backend when the field is absent, behave exactly as before (agent falls back to `ja`). If `gen-l10n` codegen output is stale, re-run `flutter gen-l10n`. If `google_fonts` cannot fetch fonts at runtime (offline), it falls back to a system font — acceptable and non-fatal; bundling the fonts as assets is a follow-up if needed. Reverting the `theme:` line in `main.dart` restores the previous Material theme without touching screen logic. No data migration is required; no destructive operations.


## Artifacts and Notes


Files expected to change or be added:

    flutter-web-app/pubspec.yaml                                  (deps: flutter_localizations, intl, google_fonts; generate: true)
    flutter-web-app/l10n.yaml                                     (new)
    flutter-web-app/lib/l10n/app_en.arb                           (new)
    flutter-web-app/lib/l10n/app_ja.arb                           (new)
    flutter-web-app/lib/l10n/app_localizations.dart               (generated)
    flutter-web-app/lib/main.dart                                 (locale + theme wiring)
    flutter-web-app/lib/locale/locale_controller.dart            (new; LocaleController + LocaleScope)
    flutter-web-app/lib/auth/auth_service.dart                    (read/default users/{uid}.language)
    flutter-web-app/lib/home/home_screen.dart                    (language switcher + localized chrome + GlassAppBar)
    flutter-web-app/lib/coordination/coordination_screen.dart    (send language in userPreference; localized + restyled)
    flutter-web-app/lib/closet/closet_screen.dart                (localized + restyled)
    flutter-web-app/lib/closet/shared_closet_gallery.dart        (localized + restyled)
    flutter-web-app/lib/history/history_screen.dart              (localized + restyled; render stored language)
    flutter-web-app/lib/auth/login_screen.dart                   (localized + restyled)
    flutter-web-app/lib/theme/app_theme.dart                     (new; Claude Design ThemeData)
    flutter-web-app/lib/theme/components.dart                    (new; EyebrowLabel, SectionCard, buttons, GlassAppBar)
    fastapi-service/app/domain/styling/value_objects.py          (UserPreference.language)
    adk-agent-service/styling_app/server.py                      (read + inject language)
    adk-agent-service/styling_app/tools/style_synthesizer.py     (language param in prompt)

Design reference: `temp-ui/flutter_ui_design_spec.md`, `temp-ui/Gen-Fashion.dc.html`.


## Interfaces and Dependencies


| Name | Location | Purpose |
|---|---|---|
| `flutter_localizations` (SDK) + `intl` | `flutter-web-app/pubspec.yaml` | First-party Flutter i18n; provides `Global*Localizations` delegates and `intl` runtime |
| `gen-l10n` / `AppLocalizations` | `flutter-web-app/l10n.yaml`, `lib/l10n/*.arb` → generated `app_localizations.dart` | Typed accessor for localized strings (`ja`/`en`) |
| `google_fonts` | `flutter-web-app/pubspec.yaml` | Loads `Archivo`, `Instrument Serif`, `Space Mono` for the design system |
| `LocaleController` / `LocaleScope` | `flutter-web-app/lib/locale/locale_controller.dart` | Holds the live `Locale`, drives `MaterialApp.locale`, and supplies the current language code to coordination runs |
| `users/{uid}.language` | Firestore (`req-phase01.md` §8.1) | Per-user chrome-language preference; read on login, written by the switcher |
| `UserPreference.language` | `fastapi-service/app/domain/styling/value_objects.py`; `sessions/{id}.userPreference.language` (Firestore) | Generation-time language, frozen per session; consumed by `adk-agent-service` and used for no-retranslation History rendering |
| `style_synthesizer(language=…)` | `adk-agent-service/styling_app/tools/style_synthesizer.py` | Generates coordinate text in the selected language |
| Claude Design tokens | `temp-ui/flutter_ui_design_spec.md`, `temp-ui/Gen-Fashion.dc.html` | Source of truth for palette, typography, shapes, and components |
