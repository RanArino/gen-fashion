# MP — Coordinate Session Persistence & Completion Notification

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.

## Purpose / Big Picture

Today, starting a coordination session in the Coordinate tab and then switching to Closet, History, or Shared and back destroys everything — the agent trace, the proposed candidates, and the generated image are all gone, and the user has to start over. This happens even though the backend has already finished (or is still working on) that generation in the background. The `ToDo` file states it plainly: "image generation should be processing async way; the process should not be stopped even if user jump to other section... the page 'Coordinate's generated results should not be disappeared... at the current state, all agent flows and generated image are gone when user go back to Coordinate page."

After this plan, a user can: start a coordination session, freely switch to any other tab while it's proposing candidates or generating the image, and come back to Coordinate to find the trace, candidates, and (if ready) the finished image exactly as they left them. If generation finishes while the user is on a different tab, an in-app notification (SnackBar) tells them, with a "View" button that jumps straight back to Coordinate. A completed session also shows up in History immediately, without needing a full page reload. This holds even in the edge case where the live event stream's own 150-second connection cap is hit before the backend actually finishes.

Separately, this plan closes a real production risk found during investigation: `adk-agent-service`'s Cloud Run deployment has no `--no-cpu-throttling` flag, so Cloud Run could throttle the CPU that the background generation task needs, right after the triggering HTTP request completes — silently stalling generation exactly in the scenario this plan is meant to make robust.

## Progress

- [x] (2026-07-05) ExecPlan authored after reading the current `HomeScreen`/`CoordinationScreen`/`HistoryScreen` Flutter code, the FastAPI session routes/state machine, the ADK agent service's background-task execution, and the Cloud Run deploy script.
- [x] (2026-07-05) `docs/req-phase02.md` §5 + ADL-037, and `docs/feature-matrix-phase02.md` MP-1...MP-7, synchronized in the same change as this plan (matrix rows set to 🟡 In progress).
- [x] (2026-07-05) MP-1 — `HomeScreen`: lazy-build `IndexedStack` (`_visitedTabs` set) keeps all four tabs' `State` alive for the app session once visited; `body: pages[_index]` replaced with `IndexedStack(index: _index, children: pages)`.
- [x] (2026-07-05) MP-2 — `CoordinationScreen`: `onSessionTerminal(sessionId, status)` callback added, fired via `_maybeNotifyTerminal()` once per session on `COMPLETED`/`ERROR`, deduped by `_notifiedTerminalSessionId`.
- [x] (2026-07-05) MP-3 — `CoordinationScreen`: `_recoverSessionState` rewritten as a bounded `while (mounted)` poll (`recoveryPollInterval`/`recoveryPollMaxWait`, gated on `session.status != 'GENERATING'`); `_generateSelected()` reordered so `_maybeOfferSaveInteresting()` only runs after the resolved status is `COMPLETED`.
- [x] (2026-07-05) MP-4 — `HistoryScreen`: optional `refreshOn` `Listenable?` param, `_load()` re-invoked via `addListener`/`removeListener` in `initState`/`dispose`.
- [x] (2026-07-05) MP-5 — `HomeScreen`: `_handleSessionTerminal` shows a `SnackBar` (skipped when already on the Coordinate tab) with a "View" action, wired via a small `_HistoryRefreshSignal extends ChangeNotifier` (needed because `notifyListeners()` is `@protected` and can't be called from outside a `ChangeNotifier` subclass); new l10n keys `coordinateReadyNotification`/`coordinateFailedNotification`/`viewAction` added to `app_en.arb`/`app_ja.arb`.
- [x] (2026-07-05) MP-6 — `scripts/deploy/deploy_adk.sh`: added `--no-cpu-throttling` plus an explanatory comment placed *before* the `gcloud run deploy` command (not inside the backslash-continued argument list, where a `#` would have swallowed the rest of the joined logical line and silently dropped later flags — caught by `bash -n` during review).
- [x] (2026-07-05) MP-7 — Tests added: 5 new cases in `coordination_screen_test.dart` (terminal-callback dedup/no-fire-on-PROPOSING/fire-once-on-COMPLETED, bounded-poll advance-and-stop, bounded-poll give-up-after-max-wait, save-Interesting-only-after-COMPLETED) plus a new `test/tab_persistence_test.dart` proving `CoordinationScreen`'s `State` survives being hidden/shown inside an `IndexedStack`. `flutter analyze`: no issues. `flutter test`: 49 passed (up from 43). Backend regression: `fastapi-service` pytest 109 passed, `adk-agent-service` pytest 60 passed (no backend files touched). Manual `make dev` browser verification not yet performed — see Outcomes.

## Surprises & Discoveries

- Observation: The backend generation pipeline is already disconnect-resilient (Firestore-backed, FastAPI `BackgroundTasks`), so no session-model or route changes are needed — this is a pure Flutter state-retention bug plus one Cloud Run deploy-config gap.
  Evidence: `adk-agent-service/styling_app/server.py`'s `POST /internal/run-session` returns `202` and dispatches `background_tasks.add_task(execute_run_session, request)`; `docs/req-phase01.md`'s "SSE 途中断の扱い" note states generation is explicitly expected to keep going and count toward the daily quota even if the SSE disconnects.
- Observation: The FastAPI SSE endpoint (`GET /sessions/{id}/stream`) is actually a 1-second poll loop capped at 150 seconds (`STREAM_POLL_SECONDS`/`STREAM_MAX_SECONDS`, `fastapi-service/app/handlers/session_routes.py:41,45`), not a Firestore `on_snapshot` listener as ADL-011 describes — a documentation/code drift worth a note but not a blocker for this plan.
- Observation: Naively wrapping all four tabs in a plain `IndexedStack` would make `HistoryScreen`/`SharedClosetGallery` fetch immediately on first load (their `initState`-driven loads would all fire at once) and, more importantly, once visited they'd never refetch again for the rest of the session — a session completed off-tab wouldn't appear in History even after opening it. Addressed by (a) lazy-building each tab's real widget only after its first visit (`_visitedTabs`), and (b) MP-4's refresh signal.
- Observation: `_generateSelected()` currently calls `_maybeOfferSaveInteresting()` before `_recoverSessionState()`; if the SSE loop ends early (synthetic timeout, never persisted to Firestore), the "save as Interesting" dialog could pop up before the coordinate image actually exists. Fixed as part of MP-3 since the new poll loop makes this ordering bug easy to hit correctly for the first time.
- Observation: `ChangeNotifier.notifyListeners()` is `@protected`/`@visibleForTesting` and cannot be called from outside a `ChangeNotifier` subclass (`flutter analyze` caught this immediately as `invalid_use_of_protected_member`/`invalid_use_of_visible_for_testing_member` when `HomeScreen` tried to call it directly on a plain `ChangeNotifier` field). Fixed by introducing a tiny `_HistoryRefreshSignal extends ChangeNotifier` with a public `fire()` method that calls `notifyListeners()` internally.
  Evidence: `flutter analyze` output for `lib/home/home_screen.dart:67:54`.
- Observation: A shell comment placed *inside* a backslash-continued command (between two `\`-terminated lines of the `gcloud run deploy` invocation) is dangerous, not just stylistically odd — bash joins backslash-continued lines into one logical line before tokenizing, so a `#` there starts a comment that swallows everything after it on that joined logical line, including all subsequent flags. Caught this while adding an explanatory comment for MP-6's `--no-cpu-throttling` flag before running `bash -n`; moved the comment above the `gcloud run deploy adk-agent-service \` line instead, then verified with `bash -n scripts/deploy/deploy_adk.sh`.
- Observation: The default 800×600 `flutter test` surface size overflows `CoordinationScreen`'s layout in `tab_persistence_test.dart`'s custom `IndexedStack` + `TextButton` harness (a `RenderFlex overflowed by 798 pixels` error, plus the `Start` button falling outside the hit-test area). Fixed the same way the existing generate/save-Interesting tests in `coordination_screen_test.dart` already do: `tester.binding.setSurfaceSize(const Size(900, 2600))` plus wrapping the `IndexedStack` in `Expanded` so the `Column` has bounded constraints.

## Decision Log

- Decision: Keep all four bottom-nav tabs mounted via a lazily-populated `IndexedStack` in `HomeScreen`, rather than introducing a state-management library (Provider/Riverpod) or hoisting session state into a new controller class.
  Rationale: The app has no state-management dependency today; `IndexedStack` is the standard, minimal Flutter idiom for "don't destroy tab state on navigation" and requires no new dependency. It also incidentally fixes the same staleness problem for Closet/History/Shared.
  Date/Author: 2026-07-05 / ExecPlan MP
- Decision: Persistence scope is in-app tab navigation only; full browser-refresh session recovery (localStorage + a new "list in-progress sessions" backend endpoint) is out of scope and tracked as a future item, not part of MP.
  Rationale: Confirmed with the user — matches the literal `ToDo` wording ("jump to other section" / "another page" reads as the SPA's own tabs, not a hard reload), and keeps this plan to a client-side fix plus one deploy flag instead of a cross-stack redesign.
  Date/Author: 2026-07-05 / User + ExecPlan MP
- Decision: Include `--no-cpu-throttling` on `adk-agent-service`'s Cloud Run deploy.
  Rationale: Without it, Cloud Run may throttle CPU after the `/internal/run-session` HTTP response is sent, starving the `BackgroundTasks` continuation that does the actual generation — directly contradicting "the process should not be stopped." Trade-off (continuous CPU billing instead of only during request handling) accepted by the user.
  Date/Author: 2026-07-05 / User + ExecPlan MP
- Decision: Fold in the History-tab live-refresh fix (MP-4) rather than leaving it as a silent regression.
  Rationale: It's a direct, non-obvious side effect of MP-1 (keep-alive tabs), not a pre-existing unrelated issue; the user opted to include it. Small: a `ChangeNotifier` signal, no new dependency.
  Date/Author: 2026-07-05 / User + ExecPlan MP
- Decision: In-app notification is a `SnackBar` from `HomeScreen`'s single root `Scaffold`; no FCM/push notification infra is added.
  Rationale: No push infra exists anywhere in the repo; "in-app notification" in the `ToDo` item is satisfied by a SnackBar, and the existing `ScaffoldMessenger.of(context)` pattern already used throughout the app resolves correctly to the one root Scaffold that spans all tabs.
  Date/Author: 2026-07-05 / ExecPlan MP
- Decision: Proceed with authoring this ExecPlan now even though the prior ExecPlan (MO, scene-aware synthesizer prompt) has one open item (MO-6, a manual visual check blocked on live Vertex AI credentials).
  Rationale: MO-6 is credential-blocked, not active in-progress work; the user explicitly asked for this plan to be created now. MO-6 stays open and tracked separately in `docs/feature-matrix-phase02.md`.
  Date/Author: 2026-07-05 / User + ExecPlan MP

## Outcomes & Retrospective

MP-1 through MP-7 are implemented and automatically verified: `flutter analyze` reports no issues; `flutter test` reports 49 passed (43 pre-existing + 6 new: 5 in `coordination_screen_test.dart`, 1 in the new `tab_persistence_test.dart`); `bash -n scripts/deploy/deploy_adk.sh` parses cleanly; `fastapi-service` pytest (109 passed) and `adk-agent-service` pytest (60 passed) are unaffected, as expected since no backend files were touched.

**Not yet done:** the manual `make dev` browser verification pass described in Validation and Acceptance (switch tabs mid-generation and confirm the trace/image persist; force off-tab completion and confirm exactly one SnackBar with a working "View" action; confirm History live-refresh; force an error path). The Cloud Run `--no-cpu-throttling` effect is also unverified — it requires a real deploy (`gcloud run services describe adk-agent-service ... --format=yaml` showing `run.googleapis.com/cpu-throttling: "false"`, plus watching Cloud Logging timestamps), not exercisable locally. Whoever runs these should update this section with the observed results.

## Context and Orientation

**Repository:** `/Users/ran/my-app/gen-fashion`. Flutter web app in `flutter-web-app/`, FastAPI backend in `fastapi-service/`, ADK agent service in `adk-agent-service/`. No state-management library is used in Flutter (`pubspec.yaml` has no provider/riverpod/bloc) — all screens are plain `StatefulWidget`/`setState`.

**Coordination session state machine** (`fastapi-service/app/domain/styling/state_machine.py`): `SOURCE_SELECTING → SEARCHING → PROPOSING → GENERATING → COMPLETED`/`ERROR`. `PROPOSING` is a deliberate pause where the user must pick candidates (`POST /sessions/{id}/select`) before `GENERATING` starts — no auto-generation without consent (ADL-027).

**The four bottom-nav tabs** live in `flutter-web-app/lib/home/home_screen.dart`: `ClosetScreen`, `CoordinationScreen`, `HistoryScreen`, `SharedClosetGallery`, selected by `_HomeScreenState._index` and a Material `NavigationBar`. Today `build()` does `final pages = [...]; ...; body: pages[_index]` — only one page widget occupies the tree at a time, so switching tabs disposes the outgoing page's `State` and constructs a fresh one on return.

**`CoordinationScreen`** (`flutter-web-app/lib/coordination/coordination_screen.dart`, ~1847 lines): `_CoordinationScreenState` holds `_events` (agent trace), `_candidates`, `_selectedCandidateIds`, `_sessionId`, `_status`, `_coordinateImageUrl`, `_running`, `_error` as plain fields — this is exactly what gets wiped when the tab is torn down. `_start()` (~line 108) creates a session and does `await for (final message in _api.streamSessionEvents(...))` (~line 147), updating state via `setState` per SSE message, then calls `_recoverSessionState()` (~line 262, currently a **one-shot** `GET /sessions/{id}` fallback) once the stream ends. `_generateSelected()` (~line 200) repeats the same pattern after `POST /sessions/{id}/select`, then (currently) calls `_maybeOfferSaveInteresting()` **before** `_recoverSessionState()`.

**SSE mechanics** (`fastapi-service/app/handlers/session_routes.py`): `GET /sessions/{id}/stream` is a 1-second poll loop (`STREAM_POLL_SECONDS = 1`, line 41) capped at 150 seconds (`STREAM_MAX_SECONDS = 150`, line 45); past the cap it emits a client-only synthetic error/timeout and closes **without** touching the real Firestore session doc, which may still complete later, invisibly to that dead connection. `adk-agent-service`'s own run timeout is 90 seconds (`adk_run_timeout_seconds`, `adk-agent-service/styling_app/config.py:69`), normally well inside the 150-second cap — except if Cloud Run CPU-throttles the background task (see MP-6).

**No existing in-app notification/toast service** beyond per-screen `ScaffoldMessenger.of(context).showSnackBar(...)` calls already used in `coordination_screen.dart` (anchor-limit, upload-queued, saved-as-interesting) and `closet_screen.dart`. Since `HomeScreen` has exactly one root `Scaffold` wrapping all four tab bodies, any descendant's `ScaffoldMessenger.of(context)` call already surfaces there — this works today only because the calling widget happens to be mounted; MP fixes the "happens to be mounted" part.

**Daily generation rate limit** (`fastapi-service/app/use_cases/styling/daily_generation_limit.py`) counts only `COMPLETED` sessions. The bounded poll loop added in MP-3 only performs `GET` reads and never calls `/select` again, so it cannot affect this counter.

## Plan of Work

### MP-1 — Keep tabs alive (`flutter-web-app/lib/home/home_screen.dart`)

Add `late final Set<int> _visitedTabs = {_index};` to `_HomeScreenState`. In the `NavigationBar.onDestinationSelected` callback, do `setState(() { _index = value; _visitedTabs.add(value); });`. In `build()`, build each tab lazily:

    final pages = [
      _visitedTabs.contains(0) ? ClosetScreen(uid: widget.uid, embedded: true) : const SizedBox.shrink(),
      _visitedTabs.contains(1) ? CoordinationScreen(uid: widget.uid, onSessionTerminal: _handleSessionTerminal) : const SizedBox.shrink(),
      _visitedTabs.contains(2) ? HistoryScreen(refreshOn: _historyRefreshSignal) : const SizedBox.shrink(),
      _visitedTabs.contains(3) ? const SharedClosetGallery() : const SizedBox.shrink(),
    ];

Replace `body: pages[_index]` with `body: IndexedStack(index: _index, children: pages)`. Once a tab's slot has rendered its real widget once, it stays that way for the rest of the app session (`_visitedTabs` only grows), so its `State` is never disposed by further nav switches. `AppConfig.e2eAutoRun` already sets the initial `_index` to `1`, so `_visitedTabs = {1}` at construction keeps existing e2e behavior (Coordinate builds immediately). `_kSectionIdByTabIndex[_index]` (help dialog) and the `_HelpIconButton` pulse animation are untouched — neither depends on the tab-swap mechanism.

### MP-2 — Terminal-state callback (`coordination_screen.dart`)

Add to `CoordinationScreen`'s constructor: `this.onSessionTerminal` (optional, `void Function(String sessionId, String status)?`). All existing call sites (`CoordinationScreen(uid: 'user-123')`, `CoordinationScreen(uid: 'user-1', api: fakeApi)` in tests) remain valid since it's optional-named.

In `_CoordinationScreenState`, add `String? _notifiedTerminalSessionId;` and a helper:

    void _maybeNotifyTerminal() {
      final sid = _sessionId;
      final status = _status;
      if (sid == null || status == null) return;
      if (status != 'COMPLETED' && status != 'ERROR') return;
      if (_notifiedTerminalSessionId == sid) return;
      _notifiedTerminalSessionId = sid;
      widget.onSessionTerminal?.call(sid, status);
    }

Call `_maybeNotifyTerminal()` right after the `setState` blocks in the `_start()`/`_generateSelected()` SSE loops, and inside the new poll loop (MP-3). Starting a new session later naturally re-arms the guard since it compares against the *current* `_sessionId`.

### MP-3 — Bounded recovery poll + save-Interesting ordering fix (`coordination_screen.dart`)

Add two more optional constructor params for test injectability, matching the existing `api`/`anchorItemsStream` pattern: `this.recoveryPollInterval = const Duration(seconds: 5)`, `this.recoveryPollMaxWait = const Duration(minutes: 5)`.

Replace the one-shot `_recoverSessionState` with a bounded loop:

    Future<void> _recoverSessionState(String sessionId) async {
      final deadline = DateTime.now().add(widget.recoveryPollMaxWait);
      while (mounted) {
        final SessionHistoryItem session;
        try {
          session = await _api.getSession(sessionId);
        } catch (e) {
          if (mounted) setState(() => _error = e);
          return;
        }
        if (!mounted) return;
        setState(() {
          _status = session.status;
          if (_candidates.isEmpty && session.proposedCandidates.isNotEmpty) {
            _candidates..clear()..addAll(session.proposedCandidates);
            if (_selectedCandidateIds.isEmpty) _applyDefaultSelection();
          }
          if (_coordinateImageUrl == null &&
              session.coordinateImageUrl != null &&
              session.coordinateImageUrl!.isNotEmpty) {
            _coordinateImageUrl = session.coordinateImageUrl;
          }
          _reportE2eState();
        });
        _maybeNotifyTerminal();
        if (session.status != 'GENERATING') return;
        if (DateTime.now().isAfter(deadline)) {
          if (mounted) {
            setState(() => _error = StateError(
                'Still generating after ${widget.recoveryPollMaxWait.inMinutes} minutes.'));
          }
          return;
        }
        await Future.delayed(widget.recoveryPollInterval);
      }
    }

Gating on `session.status != 'GENERATING'` (rather than a terminal-status allowlist) means `_start()`'s call site (status is `PROPOSING` right after the propose-phase stream) returns immediately on the first `GET` exactly as today — no behavior change there. `_generateSelected()`'s call site is the one that benefits: if the SSE closed on the synthetic (non-persisted) timeout before the real Firestore status became terminal, this loop keeps re-checking every 5 seconds for up to 5 minutes until it genuinely is, firing the notification the moment it resolves. `_running` stays `true` for the whole poll (only reset in the enclosing `finally`), so the UI's spinner/disabled state stays accurate. This only performs `GET` reads — never a new `/select` call — so the daily-generation-limit counter is untouched.

In `_generateSelected()`, swap the order so the save-Interesting dialog only offers once the resolved status is actually `COMPLETED`:

    await _recoverSessionState(sessionId);
    if (_status == 'COMPLETED') {
      await _maybeOfferSaveInteresting();
    }

### MP-4 — History live refresh (`flutter-web-app/lib/history/history_screen.dart`, `home_screen.dart`)

Add to `HomeScreen`: `final ChangeNotifier _historyRefreshSignal = ChangeNotifier();` (dispose it in `_HomeScreenState.dispose()`). Pass it into `HistoryScreen(refreshOn: _historyRefreshSignal)` (see MP-1's `pages` list). In `_handleSessionTerminal` (MP-5), call `_historyRefreshSignal.notifyListeners()` when `status == 'COMPLETED'`.

In `HistoryScreen`, add an optional constructor param `Listenable? refreshOn`. In `_HistoryScreenState.initState()`, after the existing `_load()` call, do `widget.refreshOn?.addListener(_load)`; remove it in a new `dispose()` override (`widget.refreshOn?.removeListener(_load)`). No new dependency — `ChangeNotifier`/`Listenable` are in `flutter/foundation.dart`, already transitively available via `package:flutter/material.dart`.

### MP-5 — SnackBar wiring + l10n (`home_screen.dart`, `app_en.arb`, `app_ja.arb`)

    void _handleSessionTerminal(String sessionId, String status) {
      if (status == 'COMPLETED') _historyRefreshSignal.notifyListeners();
      if (!mounted || _index == 1) return; // already on Coordinate
      final l10n = AppLocalizations.of(context)!;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(status == 'COMPLETED'
              ? l10n.coordinateReadyNotification
              : l10n.coordinateFailedNotification),
          action: SnackBarAction(
            label: l10n.viewAction,
            onPressed: () => setState(() => _index = 1),
          ),
        ),
      );
    }

Add to both `flutter-web-app/lib/l10n/app_en.arb` and `app_ja.arb` (matching the existing key/`@key` convention, e.g. near `uploadFailed`/`savedAsInteresting`):

    "coordinateReadyNotification": "Your coordinate is ready.",
    "coordinateFailedNotification": "Coordinate generation failed.",
    "viewAction": "View"

with Japanese equivalents (e.g. "コーディネートが完成しました。" / "コーディネートの生成に失敗しました。" / "表示"). `pubspec.yaml` has `flutter: generate: true`, so `flutter test`/`flutter pub get` auto-regenerates `app_localizations*.dart` — do not hand-edit the generated files.

### MP-6 — Cloud Run deploy fix (`scripts/deploy/deploy_adk.sh`)

Line 63, add the flag right after `--cpu=1 \`:

      --cpu=1 \
      --no-cpu-throttling \

This cannot be exercised locally (CPU throttling is Cloud Run-only, no docker-compose equivalent); see Validation and Acceptance for what to check instead.

### MP-7 — Tests

`test/coordination_screen_test.dart` — existing tests untouched (new constructor params are optional-named). Add:
- Callback fires exactly once with `('session-1', 'COMPLETED')` when Start → Generate completes (extend `_FakeCoordinationApiClient` with an `onSessionTerminal` capture list).
- Callback does not fire after only `_start()` (status stays `PROPOSING`).
- Poll loop advances and stops: fake `getSession` returns `GENERATING` once then `COMPLETED`; use `recoveryPollInterval: Duration(milliseconds: 10)`; assert final status `COMPLETED` and one callback firing.
- Poll loop gives up after `recoveryPollMaxWait`: fake `getSession` always `GENERATING`; tiny durations; assert an error surfaces, no infinite pump/hang.
- Save-Interesting dialog only appears when resolved status is `COMPLETED` (covers the MP-3 reordering).

New file `test/tab_persistence_test.dart` — a Firebase-free harness proving the keep-alive mechanism itself: a `StatefulBuilder` holding an `int index` plus `IndexedStack(index: index, children: [CoordinationScreen(uid: 'user-1', api: fakeApi), const Placeholder()])`; start a session in the fake API, flip `index` away and back, assert the trace/candidates/result are still present (i.e., `_CoordinationScreenState` was never disposed). `HomeScreen` itself has no Firebase-mocking test seam today (no `fake_cloud_firestore`/similar dev dependency) — full `HomeScreen` widget-test coverage of the lazy-tab-build/SnackBar wiring is out of scope for this plan; it's covered by the manual pass below instead.

## Concrete Steps

Working directory: `/Users/ran/my-app/gen-fashion`.

1. `flutter-web-app/lib/home/home_screen.dart`: add `_visitedTabs`, `_historyRefreshSignal`, lazy `pages`, `IndexedStack`, `_handleSessionTerminal`.
2. `flutter-web-app/lib/coordination/coordination_screen.dart`: add `onSessionTerminal`/`recoveryPollInterval`/`recoveryPollMaxWait` params, `_notifiedTerminalSessionId` + `_maybeNotifyTerminal()`, rewrite `_recoverSessionState` as the bounded loop, reorder save-Interesting in `_generateSelected()`.
3. `flutter-web-app/lib/history/history_screen.dart`: add `refreshOn` param + listener wiring.
4. `flutter-web-app/lib/l10n/app_en.arb` and `app_ja.arb`: add the three new keys.
5. `scripts/deploy/deploy_adk.sh`: add `--no-cpu-throttling`.
6. Add/extend tests per MP-7.
7. From `flutter-web-app/`: `flutter pub get && flutter analyze && flutter test`.
8. From repo root: `bash -n scripts/deploy/deploy_adk.sh` (parse check).
9. Local manual verification via `make dev` (see Validation and Acceptance).

## Validation and Acceptance

**Automated:**
- `flutter analyze` — no new issues.
- `flutter test` — all existing tests plus the new ones in `coordination_screen_test.dart` and `tab_persistence_test.dart` pass.
- `bash -n scripts/deploy/deploy_adk.sh` — script still parses after the flag addition.
- No `fastapi-service`/`adk-agent-service` code changes in this plan, so their existing pytest suites are unaffected (run them anyway as a regression check: `pytest fastapi-service/tests -q`, `pytest adk-agent-service/styling_app/tests -q`).

**Manual (local, via `make dev`):**
1. Sign in, open Coordinate, start a Standard generation against a shared closet.
2. While status is `SEARCHING`/`PROPOSING`, switch to Closet, then History, then back to Coordinate — trace panel, candidate list, and running indicator are unchanged, not reset.
3. Select candidates, hit Generate, immediately switch to another tab; wait for the backend to actually finish (watch logs or the Firestore session doc); confirm exactly one SnackBar appears ("Your coordinate is ready.") with a "View" action; tapping it jumps to Coordinate showing the finished image with no restart needed.
4. Confirm the completed session now also appears in History without a full page reload (MP-4).
5. Force an error path (e.g., stop `adk-agent-service` mid-run) and confirm the failure-variant SnackBar text and that "View" shows the error state in the trace panel.
6. Cloud Run CPU-throttling fix (MP-6) is **not** locally verifiable — see Idempotence and Recovery for the post-deploy check.

**Acceptance:** all of the above manual steps observe the described behavior, and the automated checks in this section pass.

## Idempotence and Recovery

All Flutter/deploy-script changes are plain edits, safe to re-run `flutter analyze`/`flutter test`/`bash -n` any number of times. The `--no-cpu-throttling` deploy flag is idempotent — re-running `deploy_adk.sh` against the same image just redeploys the same Cloud Run revision config. Its actual effect can only be confirmed after a real deploy:

    gcloud run services describe adk-agent-service --project <PROJECT> --region asia-northeast1 --format=yaml

confirming the revision template carries `run.googleapis.com/cpu-throttling: "false"`; and by watching Cloud Logging for `execute_run_session` timestamps to confirm generation reliably finishes within its 90-second budget even though the initiating HTTP response already returned. If a regression is suspected, redeploy without the flag to compare — no data migration or destructive step is involved either way.

## Artifacts and Notes

`docs/req-phase02.md` §5 and ADL-037, and `docs/feature-matrix-phase02.md`'s MP section, were added in the same change as this plan's authoring (2026-07-05) — see those files directly rather than duplicating their text here, so they stay the single source of truth as this plan evolves.

`docs/architecture-overview.md` requires **no update** for this plan: it changes internal state-retention/notification behavior within the already-diagrammed `flutter_acc` component and a deploy flag on the already-diagrammed `adk` component; it adds no new component, port/adapter, data store, or external service, and moves nothing across the implemented/planned boundary.

## Interfaces and Dependencies

- **Flutter/Dart:** `IndexedStack`, `ChangeNotifier`/`Listenable` (both `flutter/foundation.dart`, already available) — no new packages.
- **Existing backend endpoints reused as-is, no changes:** `GET /sessions/{id}` (`fastapi-service/app/handlers/session_routes.py:210`), `GET /sessions/{id}/stream` (line 332), `POST /sessions/{id}/select` (line 241).
- **Deploy tooling:** `gcloud run deploy` flag `--no-cpu-throttling` (`scripts/deploy/deploy_adk.sh`).
- **l10n:** `flutter gen-l10n` (invoked automatically via `pubspec.yaml`'s `flutter: generate: true` on `flutter pub get`/`flutter test`/`flutter build`).
