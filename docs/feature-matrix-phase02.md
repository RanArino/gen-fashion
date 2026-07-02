# Phase 2 Feature Matrix — gen-fashion

> **Source of truth:** [req-phase02.md](req-phase02.md)

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

