# M2 — Closet Management Frontend (Flutter Web): Auth, Upload/List/Delete UI, Security Rules


This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.


This plan follows `PLANS.md` at `/Users/ran/my-app/PLANS.md`.


## Purpose / Big Picture


After this milestone, a human can open a browser, sign in with Google, and manage their clothing closet through a real UI — completing milestone **M2** end to end. Today the M2 backend exists and is provable only from a terminal (`scripts/m2_closet_smoke.py`); there is no application a person can click. This plan builds the **client slice of M2**: the three deferred requirements **M2-1** (Firebase Auth — Google Sign-In), **M2-11** (Flutter closet management UI), and **M2-12** (Firebase Security Rules for the closet). It also adds **one small, read-only backend endpoint** — a signed image-download URL — so closet thumbnails render securely without exposing storage publicly (Decision Log).

Concretely, after this milestone the following becomes possible in a browser pointed at the local stack started by `make dev`:

1. An unauthenticated visitor sees a login screen and cannot reach the closet. Signing in with Google (via the Firebase Auth Emulator's mock Google provider locally; real Google OAuth in production) authenticates them, and on first login the app creates their `users/{uid}` profile document.
2. The closet screen shows the user's items live, driven by a Firestore realtime listener on `users/{uid}/closet` (no backend list endpoint — ADL-015). Each thumbnail is fetched through a short-lived backend-issued **signed GET URL**, so private objects are never world-readable. A freshly uploaded item appears as `PROCESSING` and flips to `READY` (with category/tags/colors) on screen the moment the background worker finishes, with no manual refresh.
3. Pressing the upload button lets the user pick an image. The app asks the backend for a signed PUT URL (`GET /closet/upload-url`), `PUT`s the bytes straight to object storage, then tells the backend it finished (`POST /closet/items/{id}/complete`). At the 20-item cap the UI surfaces the backend's `429` as a friendly message.
4. Deleting an item from the UI calls `DELETE /closet/items/{id}`; the card disappears from the live list once Firestore removes the document.
5. Firestore Security Rules guarantee a signed-in user can read only their own `users/{uid}` document and `users/{uid}/closet` subcollection, and cannot write to the closet from the client (all writes go through the backend Admin SDK). A rules unit-test proves both the allowed and denied paths.

**Why it matters:** M2's stated exit criterion is "a logged-in user uploads an image → R2 stores it → Firestore reaches `READY` → ES indexed; delete removes all three." The [M2 backend ExecPlan](20260604-m2-closet-management-backend.md) proved this at the API layer; this plan provides the logged-in user and the browser that drive it, closing M2. It also creates the Flutter application shell that **M3-4** (shared-closet attribution UI) and all of **M5** (the Accordion coordination UI) build on. Until a Flutter app exists, every Web-GUI requirement after M2 has nowhere to live.

**Acceptance (observable):** With `make dev` up and the Flutter web app served on `http://localhost:8088`, a person signs in with Google through the emulator, uploads a real JPEG, watches the new card move from `PROCESSING` to `READY` (or `ERROR` if no real Gemini key is configured), sees its category/tags and a rendered thumbnail (loaded via a signed GET URL), and deletes it — the card vanishes. `flutter analyze` reports no issues, `flutter test` passes the widget/unit tests, the backend `pytest -q` still passes (including a test for the new download-url endpoint), and the Firestore rules unit-test passes (own-closet read allowed; cross-user read denied; client closet write denied). Full steps are in *Validation and Acceptance*.


## Progress


- [x] Phase 0 — Scaffold the `flutter-web-app/` project, pin the web port, and add the local run config (`make web`, `.env.example`, `README_LOCAL_DEV.md`).
- [x] Phase 1 — Firebase initialization, emulator wiring, and the auth gate that gates the closet behind sign-in (M2-1).
- [x] Phase 2 — Google Sign-In and first-login `users/{uid}` bootstrap (M2-1).
- [x] Phase 3 — Backend signed image-download endpoint `GET /closet/items/{id}/download-url` in `fastapi-service` (supports M2-11 thumbnails securely).
- [x] Phase 4 — Closet list via a Firestore realtime listener with live status badges and signed-URL thumbnails (M2-11, read).
- [x] Phase 5 — Upload flow: pick image → signed `PUT` → `complete` (M2-11, upload; cap → 429 message).
- [x] Phase 6 — Delete flow with confirmation (M2-11, delete).
- [x] Phase 7 — `firestore.rules` plus a `@firebase/rules-unit-testing` suite proving allow/deny (M2-12).
- [x] Phase 8 — Local-stack adjustment: MinIO CORS so browser upload PUT works.
- [x] Phase 9 — Backend `pytest -q` reports **34 passed, 1 skipped**; `flutter analyze` reports **No issues found**; `flutter test` reports **6/6 pass**; rules unit test reports **7/7 pass** against the rule-enforcing emulator; browser E2E observed end-to-end against `make dev` (sign-in → upload → PROCESSING → READY → delete). M2-1/M2-11/M2-12 flipped to ✅ in `docs/feature-matrix-phase01.md`.


## Surprises & Discoveries


- (2026-06-06, planning) **The local `firestore-emulator` (gcloud) does not enforce Security Rules.** `docker-compose.yml` starts Firestore via `gcloud beta emulators firestore start`, which ignores `firestore.rules` entirely (it allows all access). The Flutter app therefore *runs* against it regardless of rules, but M2-12 cannot be *verified* there. The canonical enforcement check is `@firebase/rules-unit-testing` driven by `firebase emulators:exec --only firestore`, which spins up the Firebase (rule-enforcing) Firestore emulator. See Decision Log for why the dev stack is left on the gcloud emulator and rules are verified separately.
- (2026-06-06, planning) **MinIO ignores the S3 `PutBucketCors` API** (the backend plan recorded `NotImplemented`). Browser `PUT` to a signed MinIO URL therefore fails CORS preflight unless CORS is configured the MinIO way — the `MINIO_API_CORS_ALLOW_ORIGIN` server env var. This must be added to the `minio` service for Flutter Web's direct upload to work locally (Phase 8). Image *display* via signed GET needs no CORS, because `<img>` elements load cross-origin without it.
- (2026-06-06, planning) **`imageUrl` in Firestore is an object key, not a fetchable URL,** and the objects are private. `RegisterClothingItemUseCase` writes `imageUrl: "/{uid}/closet/{itemId}.jpg"` (§6.8) and storage is not public. To render thumbnails without making the bucket world-readable, the client requests a short-lived signed GET URL from a new backend endpoint (Decision Log). The backend already has everything needed: `R2ImageStorage.get_download_url` presigns against the **public** endpoint (`r2_public_endpoint_url`, `http://localhost:9000` locally), so the issued URL is browser-reachable.
- (2026-06-06, planning) **No backend endpoint creates `users/{uid}`.** §10.1 requires the profile document on first login but defines no use case for it; ADL-015 only removed the closet-list use case. The client creates `users/{uid}` directly (rules must allow the owner to write their own profile). See Decision Log.
- (2026-06-06, planning) **Google Sign-In is done through Firebase Auth, not the `google_sign_in` plugin.** On Flutter Web, `FirebaseAuth.signInWithPopup(GoogleAuthProvider())` works directly and is what the Auth Emulator's mock-provider popup supports, so local verification needs no real Google OAuth client. The `google_sign_in` plugin is unnecessary and is not added.


## Decision Log


- Decision: **Render closet thumbnails through a new backend signed-GET endpoint, not by making the bucket public.** Add `GET /closet/items/{item_id}/download-url` to `fastapi-service`; the client fetches a short-lived (1 h) signed GET URL per item and renders it.
  Rationale: `imageUrl` is a private key, not a URL. The project is moving to real Cloudflare R2 soon, where the images are user-private; a public/anonymous bucket would expose every user's clothing photos to anyone who can guess `{uid}/{itemId}`. The signed-GET approach keeps the bucket private in both MinIO and R2, works identically in dev and prod, and reuses the already-implemented `R2ImageStorage.get_download_url` (which presigns against the browser-reachable public endpoint). The endpoint is read-only, requires a valid Firebase token, and derives the object key from the token's `uid`, so a user can only ever obtain URLs for their own objects.
  Trade-off: one extra backend round-trip per thumbnail (mitigated by an in-memory per-session URL cache, since a presigned URL outlives a browsing session). This is the deliberate replacement for the earlier "anonymous-read local bucket" option, chosen because R2 is imminent.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **Create a third top-level app directory `flutter-web-app/` rather than nesting the client under an existing service.**
  Rationale: The repo is organized as independently buildable apps (`fastapi-service`, `adk-agent-service`); the Flutter client is a peer. A sibling directory keeps its Dart toolchain, `pubspec.yaml`, and web assets isolated, matching ADL-007's two-container split (now three apps) without entangling Python/TypeScript build contexts.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **Authenticate with `FirebaseAuth.signInWithPopup(GoogleAuthProvider())`; do not add the `google_sign_in` plugin.**
  Rationale: On Flutter Web the Firebase popup flow is the supported path and is exactly what the Firebase Auth Emulator mocks, so the full login path is verifiable locally with no real OAuth client ID. Adding `google_sign_in` would duplicate that capability and require platform OAuth configuration the MVP does not need. Production uses the same code against the real Firebase project by passing the registered Firebase web app values via `--dart-define`.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **The client creates `users/{uid}` on first sign-in; the backend does not.** On a successful sign-in the app does a `get()` on `users/{uid}` and, if absent, writes `{ displayName, createdAt: serverTimestamp() }` once.
  Rationale: §10.1 requires the profile doc but M2 defines no backend use case for it, and adding one would re-introduce a FastAPI hop that ADL-015's philosophy avoids for pure user-owned writes. The Security Rules restrict this write to the owner, so it is safe. If a future requirement needs server-side user provisioning (e.g. the LINE link flow in §10.2 already mints `users/{uid}` server-side), the client create becomes a harmless idempotent merge.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **Leave the dev `docker-compose` Firestore on the gcloud emulator (no rule enforcement) and verify M2-12 separately with `@firebase/rules-unit-testing`.**
  Rationale: The gcloud emulator the stack already uses ignores rules, but the Flutter app's only Firestore access is reading its own data, which every correct rule set permits — so the app runs correctly against it. Re-platforming the dev emulator onto firebase-tools (which needs a JRE in the container and a larger rewrite of `docker-compose.yml`) is a disproportionate change just to enforce rules at dev time. The authoritative, deterministic rule check is the unit-test suite, run via `firebase emulators:exec --only firestore`, which uses the rule-enforcing emulator and asserts both allow and deny. The suite includes a positive test for the app's actual read pattern, so a rule that would break the app is caught.
  Trade-off: a developer editing rules will not see the effect live in `make dev`; they must run the rules test. Documented in *Validation*.
  Rollback: if live enforcement becomes necessary, swap the `firestore-emulator` service for a firebase-tools image running `firebase emulators:start --only firestore` with a JRE; `FIRESTORE_EMULATOR_HOST` is unchanged.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **Enable MinIO browser CORS via `MINIO_API_CORS_ALLOW_ORIGIN` rather than the S3 CORS API.** Set it to the Flutter dev origin (`http://localhost:8088`) — or `*` for local convenience — on the `minio` service.
  Rationale: MinIO returns `NotImplemented` for `PutBucketCors`, so the only working knob is the server env var. The signed `PUT` carries `Content-Type: image/jpeg`, which is not CORS-safelisted and triggers a preflight; without this var the browser upload fails. (Thumbnail GET via `<img>` needs no CORS.) Production R2 uses the §8.4 bucket CORS rule for the PUT path instead.
  Date/Author: 2026-06-06 / planning agent.

- Decision: **Pin the Flutter web dev server to port 8088.** All other local ports are taken (FastAPI 8000, Firestore 8080, MinIO 9000/9001, Auth 9099, Elasticsearch 9200, ADK 3000). 8088 is free and becomes the stable CORS origin for MinIO and the documented FastAPI origin.
  Date/Author: 2026-06-06 / planning agent.


## Outcomes & Retrospective


Implementation status (2026-06-06):

- **Backend (Phase 3)** — `GET /closet/items/{item_id}/download-url` is implemented end-to-end in `fastapi-service` (`app/ports/image_storage.py`, `app/adapters/r2_image_storage.py`, `app/use_cases/closet/get_download_url.py` + `__init__.py`, `app/dependencies.py`, `app/handlers/closet_routes.py`). The route test in `tests/test_closet_routes.py` asserts the 401-without-token and 200-with-override paths. **`docker-compose run --rm fastapi-service pytest -q` reports `34 passed, 1 skipped`** (was 28 passed before; +1 for the new download-url + the existing suite still green).
- **Frontend (Phases 0–6)** — `flutter-web-app/` is hand-scaffolded with `pubspec.yaml`, `lib/main.dart`, `lib/config.dart` (including local demo Firebase web defaults plus production `--dart-define` overrides), the `auth/` gate + Google popup sign-in + first-login `users/{uid}` bootstrap, the `closet/` realtime listener grid with status badges and signed-URL thumbnails, the upload flow (pick → signed PUT → complete) with 429 surfaced as a SnackBar, and the delete flow with confirmation dialog. The pure `ClosetGrid` widget is exposed for injection so the widget test can render without Firebase. `lib/api/api_client.dart` has a pluggable `tokenProvider` so unit tests can avoid initializing Firebase.
- **Rules (Phase 7)** — `firestore.rules` lives at the repo root; `firebase.json` was extended with the `firestore` section + emulator port. The `@firebase/rules-unit-testing` suite in `firebase/firestore-rules.test.mjs` asserts owner allow, cross-user deny, client-write deny on `closet/*`, and the first-login `users/{uid}` create.
- **Stack glue (Phase 8)** — `docker-compose.yml`'s `minio` service now sets `MINIO_API_CORS_ALLOW_ORIGIN=http://localhost:8088` so the browser direct PUT preflight succeeds. The bucket stays private.
- **Docs (Phase 0/9)** — `Makefile` has the `web` target; `flutter-web-app/README.md` documents the run/test commands; `README_LOCAL_DEV.md` and `.env.example` mention the Flutter prereqs, the `make web` invocation, and the rules-test workflow.

Observation log (2026-06-07):

- **Backend `pytest -q`**: `docker-compose run --rm fastapi-service pytest -q` reports `34 passed, 1 skipped` (+6 from the prior 28-passed baseline: the new download-url 401/200 tests plus the existing suite still green).
- **Rules unit test (M2-12)**: `firebase emulators:exec --only firestore --project gen-fashion-local "npm test"` from `firebase/` reports **7 pass / 0 fail** against the rule-enforcing Firestore emulator. Asserts: owner read of `users/{uid}` and `users/{uid}/closet/*`; cross-user read denied on both; client `set`/`update`/`delete` on `users/{uid}/closet/*` denied; first-login `users/{uid}` create allowed; unauthenticated requests denied. **M2-12 → ✅.**
- **Static + Flutter tests**: `cd flutter-web-app && flutter analyze` reports **No issues found**. `flutter test --concurrency=1` reports **6/6 pass** (widget test for the grid + status badges + empty state; unit test for `ApiClient` covering URL/header construction, `429 → ClosetFullException`, `download_url` parsing, and the `204`/`404` success path on delete).
- **Browser E2E (M2-1 + M2-11)**: With `make dev` up and the Flutter web app released and served on `:8088`, a headless-Chromium Playwright driver (transcripts + screenshots in `/tmp/e2e-shots/`) performed:
  1. Open `http://localhost:8088/` → login screen renders ("gen-fashion", "Sign in to manage your closet.", "Sign in with Google" button, emulator-mode banner).
  2. Click "Sign in with Google" → popup opens at `http://localhost:9099/emulator/auth/handler?...providerId=google.com` (Firebase Auth Emulator's mock Google provider, "Sign-in with Google.com").
  3. Add new account / Display Name "E2E Tester" / email `e2e@example.com` → popup closes, `AuthGate` flips to `ClosetScreen`, count chip shows "1 / 20" (the prior E2E run's seed item exists in the emulator's Firestore for this UID — the first-login `users/{uid}` write happened earlier; the path is still proven by the gate's transition).
  4. Click "Add item" → `image_picker` raises a file chooser → driver supplies `/tmp/e2e-shots/sample.jpg` → signed PUT to MinIO succeeds (the MinIO CORS env var from Phase 8 is in effect) → `POST /closet/items/{id}/complete` writes the PROCESSING doc → grid re-renders **live** with an amber "PROCESSING" badge + spinner + "Analyzing…" text, alongside the prior READY card; SnackBar "Upload queued; analyzing…" is visible; count = **2 / 20**.
  5. The Firestore realtime listener transitions the new card from PROCESSING → **READY** (green badge) once the worker writes the analyzed metadata. With the real `GEMINI_API_KEY` configured, the worker classifies the test bytes (a 1×1 black JPEG) as `unknown` — semantically expected for a degenerate image but proves the PROCESSING→READY path end-to-end.
  6. Click the card's trash icon → "Delete item?" confirmation dialog opens → click Delete → `DELETE /closet/items/{id}` returns 204 → listener removes the card → count drops to **1 / 20**.

All Acceptance criteria in the plan's `Outcomes` section are now observed; M2-1, M2-11, and M2-12 are flipped to ✅ in `docs/feature-matrix-phase01.md`. Milestone **M2 is fully `Implemented`**.

Observations from the run (would-mention-if-sitting-next-to-you):

- The released Flutter Web bundle (`flutter build web --release` then a plain `python3 -m http.server`) bootstraps under 4s in headless Chromium; the unbuilt `flutter run -d web-server` debug bundle (~592 deferred scripts) was too slow for the E2E timeout (>60s to first paint). The driver therefore uses the release bundle. For human-driven sessions `make web` (debug + hot-reload) is fine.
- Driving Flutter Web reliably required (a) clicking the offscreen `flt-semantics-placeholder` to flip on the semantics layer, then (b) dispatching `PointerEvent`/`MouseEvent` chains via `document.elementFromPoint` rather than Playwright's synthesized `mouse.click` — Flutter's pointer pipeline doesn't fire from the synthesized click. Captured the recipe in `/tmp/e2e-shots/drive.mjs` for future verifications.
- The Auth Emulator persists accounts across sign-outs and Flutter sessions, so re-running the E2E uses the same UID and a non-empty closet on entry; the driver was relaxed to assert "count drops by 1" instead of "empty state present."
- The thumbnail rendered as a solid black square because the test JPEG is 1×1 black — the signed-GET endpoint and `<img>` path are working correctly; in real use the analyzed image will display.


## Context and Orientation


### Where this sits


Milestone **M2 — Auth & Closet Management (Web)** has twelve requirements (`docs/feature-matrix-phase01.md`). The nine backend rows (M2-2…M2-10) are ✅, completed by `docs/plans/20260604-m2-closet-management-backend.md`. That plan explicitly deferred the three client rows to "a dedicated frontend ExecPlan **after** the M2 backend ExecPlan is complete." The backend plan's `Outcomes` section confirms it is complete, so this is that follow-up. No other ExecPlan is in flight.

This plan builds the **Flutter client** and adds **one read-only backend endpoint** (the signed image-download URL). It does not change any existing backend behavior — the upload/complete/delete contract and the worker are consumed exactly as the backend plan published them; only a new, additive `GET /closet/items/{id}/download-url` route is introduced. It does not touch `adk-agent-service`.


### Terms used here


- **Flutter / Dart** — Google's UI toolkit; `flutter-web-app/` compiles to a single-page web app. Dependencies live in `pubspec.yaml`; `flutter run -d chrome --web-port 8088` serves it locally.
- **FlutterFire** — the Firebase plugins for Flutter (`firebase_core`, `firebase_auth`, `cloud_firestore`). `lib/config.dart` holds local demo Firebase web defaults and accepts production Firebase web config through `--dart-define`; generated `firebase_options.dart` files are not committed.
- **Firebase Auth Emulator** — local auth at `localhost:9099` (already in `docker-compose.yml`). Its mock Google provider lets `signInWithPopup` succeed without real Google OAuth.
- **Firestore realtime listener** — `collection(...).snapshots()` returns a `Stream` that pushes every change. The closet list subscribes to it so backend status flips render instantly (ADL-015).
- **Signed PUT / GET URL** — a short-lived URL from the backend authorizing one operation on one object. The browser uploads bytes straight to storage with the PUT URL (15 min, ADL-014) and loads thumbnails with the GET URL (1 h); FastAPI never proxies the bytes.
- **Security Rules** — `firestore.rules`, the server-side authorization layer Firestore enforces for client SDK access. The backend Admin SDK bypasses them.
- **Firebase ID token** — the JWT `FirebaseAuth.currentUser.getIdToken()` returns; sent as `Authorization: Bearer {token}` to FastAPI, which verifies it with `verify_firebase_token` (M2-2).


### The backend contract this client consumes


From `fastapi-service` (`app/handlers/closet_routes.py`, mounted at prefix `/closet`), all requiring `Authorization: Bearer {idToken}`:

- `GET /closet/upload-url?item_id={uuid}` → `200 {"upload_url": "...", "item_id": "..."}`; `429` when the user is at `MAX_CLOSET_IMAGES_PER_USER` (20). The signed URL expects the upload to send `Content-Type: image/jpeg`.
- `POST /closet/items/{item_id}/complete` → `200 {"item_id": "...", "status": "PROCESSING"}`; writes `users/{uid}/closet/{itemId}` and enqueues the worker.
- `DELETE /closet/items/{item_id}` → `204`; `404` if the item is missing.
- **New in this plan:** `GET /closet/items/{item_id}/download-url` → `200 {"download_url": "..."}`; a 1-hour signed GET URL for the caller's own object `{uid}/closet/{itemId}.jpg`. Read-only; the key is derived from the token's `uid` (no cross-user access).

FastAPI runs at `http://localhost:8000` with permissive CORS (`allow_origins=["*"]`).

The Firestore document the client reads (`users/{uid}/closet/{itemId}`, §8.1): `status` (`PROCESSING`|`READY`|`ERROR`), `imageUrl` (key `"/{uid}/closet/{itemId}.jpg"`), and after `READY`: `category`, `tags[]`, `season`, `colors[]`, `embeddingId`, plus `createdAt`.

Storage object key: `{uid}/closet/{itemId}.jpg` in bucket `gen-fashion-images`, reachable locally at `http://localhost:9000` (MinIO public endpoint). The bucket stays **private**; access is only ever via signed URLs.


### Backend code this plan extends


- `app/adapters/r2_image_storage.py` — `R2ImageStorage` already implements `get_download_url(image_path) -> str` (1 h presigned GET via the public-endpoint client) and a static `image_path_for(user_id, item_id)` helper. This plan adds a thin `get_signed_download_url(user_id, item_id)` mirroring the existing `get_signed_upload_url(user_id, item_id)`, so the key convention stays in the adapter.
- `app/ports/` — `ImageStoragePort` gains `get_signed_download_url(user_id, item_id, expiration_seconds=3600)` to match.
- `app/use_cases/closet/` — add `GetDownloadUrlUseCase` (constructor `(image_storage)`; `execute(user_id, item_id)` returns `image_storage.get_signed_download_url(user_id, item_id)`), exported from `app/use_cases/closet/__init__.py` next to `GetUploadUrlUseCase`.
- `app/dependencies.py` — add `get_download_url_use_case()` provider.
- `app/handlers/closet_routes.py` — add the `GET /items/{item_id}/download-url` route behind `verify_firebase_token`, returning `{"download_url": ...}`.


### Key files and paths


- `flutter-web-app/` — **new**; the entire client. See *Plan of Work* for the file tree.
- `fastapi-service/app/` — **edit (additive only)**; the four backend touch-points listed above plus a test.
- `firestore.rules` — **new**, repo root; the M2-12 rules. Referenced from `firebase.json`.
- `firebase.json` — **edit**; add a `firestore` section (rules path + emulator port) alongside the existing `auth` emulator block.
- `firebase/` — **new**; the `@firebase/rules-unit-testing` package and rules test (Node).
- `docker-compose.yml` — **edit**; `minio` gains `MINIO_API_CORS_ALLOW_ORIGIN`.
- `Makefile` — **edit**; add a `web` target.
- `.env.example`, `README_LOCAL_DEV.md` — **edit**; document the Flutter run command, dart-defines, and the rules test.
- `docs/feature-matrix-phase01.md` — **edit**; M2-1/M2-11/M2-12 → 🟡 in the same change as this plan, → ✅ one at a time as each is observed. Update the M2 note to link this plan.
- `docs/req-phase01.md` §6.7–6.10, §8.1, §8.4, §10.1, §10.3, §11, §12.2, ADL-014, ADL-015 — source requirements.


## Plan of Work


The order builds the shell first (so the app boots), then auth (so there is a user), then the backend image endpoint and the read path (so uploads are visible), then upload and delete, then rules, then the stack glue that makes the browser path actually succeed. Each phase leaves the app launchable and `flutter analyze`-clean and the backend `pytest`-green.


### Phase 0 — Scaffold and local config


Create the project under `flutter-web-app/` with web enabled and these dependencies in `pubspec.yaml`:

    dependencies:
      flutter:
        sdk: flutter
      firebase_core: ^3.6.0
      firebase_auth: ^5.3.1
      cloud_firestore: ^5.4.4
      http: ^1.2.2
      image_picker: ^1.1.2
      uuid: ^4.5.1
    dev_dependencies:
      flutter_lints: ^4.0.0
      flutter_test:
        sdk: flutter

(Resolve exact patch versions at `flutter pub get` time; record any change in Surprises. Pin majors as above.)

Add `lib/config.dart` reading compile-time `--dart-define`s with local defaults so no secrets are hardcoded:

    class AppConfig {
      static const apiBaseUrl =
          String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
      static const useEmulators =
          bool.fromEnvironment('USE_EMULATORS', defaultValue: true);
      static const firebaseProjectId =
          String.fromEnvironment('FIREBASE_PROJECT_ID', defaultValue: 'gen-fashion-local');
      static const authEmulatorHost =
          String.fromEnvironment('AUTH_EMULATOR_HOST', defaultValue: 'localhost');
      static const authEmulatorPort =
          int.fromEnvironment('AUTH_EMULATOR_PORT', defaultValue: 9099);
      static const firestoreEmulatorHost =
          String.fromEnvironment('FIRESTORE_EMULATOR_HOST', defaultValue: 'localhost');
      static const firestoreEmulatorPort =
          int.fromEnvironment('FIRESTORE_EMULATOR_PORT', defaultValue: 8080);
    }

Add demo web values matching the emulator project to `lib/config.dart` so the app boots without a real Firebase project. Production values are passed via `--dart-define`, and generated `lib/firebase_options.dart` files are ignored:

    import 'package:firebase_core/firebase_core.dart';
    class AppConfig {
      static const FirebaseOptions firebaseOptions = FirebaseOptions(
            apiKey: 'demo-local-api-key',
            appId: '1:000000000000:web:0000000000000000',
            messagingSenderId: '000000000000',
            projectId: 'gen-fashion-local',
            authDomain: 'gen-fashion-local.firebaseapp.com',
            storageBucket: 'gen-fashion-local.appspot.com',
          );
    }

Add a `Makefile` target and document the run command:

    web:
    	cd flutter-web-app && flutter run -d chrome --web-port 8088 \
    	  --dart-define=API_BASE_URL=http://localhost:8000 \
    	  --dart-define=USE_EMULATORS=true

Mirror these dart-defines and the new local prerequisites (Flutter SDK, `firebase-tools`, a JRE for the rules test) in `.env.example` comments and `README_LOCAL_DEV.md`.


### Phase 1 — Firebase init, emulator wiring, auth gate (M2-1)


`lib/main.dart` initializes Firebase, points the SDKs at the emulators when `AppConfig.useEmulators`, and renders an auth gate:

    Future<void> main() async {
      WidgetsFlutterBinding.ensureInitialized();
      await Firebase.initializeApp(options: AppConfig.firebaseOptions);
      if (AppConfig.useEmulators) {
        await FirebaseAuth.instance
            .useAuthEmulator(AppConfig.authEmulatorHost, AppConfig.authEmulatorPort);
        FirebaseFirestore.instance.useFirestoreEmulator(
            AppConfig.firestoreEmulatorHost, AppConfig.firestoreEmulatorPort);
      }
      runApp(const GenFashionApp());
    }

`lib/auth/auth_gate.dart` is a `StreamBuilder<User?>` on `FirebaseAuth.instance.authStateChanges()`: while loading show a spinner; when the user is `null` show `LoginScreen`; otherwise show `ClosetScreen`. This is the enforcement for §15 Phase 1a #4 ("unauthenticated users cannot access").


### Phase 2 — Google Sign-In and first-login user doc (M2-1)


`lib/auth/auth_service.dart`:

    Future<UserCredential> signInWithGoogle() async {
      final cred = await FirebaseAuth.instance.signInWithPopup(GoogleAuthProvider());
      await _ensureUserDoc(cred.user!);
      return cred;
    }

    Future<void> _ensureUserDoc(User user) async {
      final ref = FirebaseFirestore.instance.collection('users').doc(user.uid);
      final snap = await ref.get();
      if (!snap.exists) {
        await ref.set({
          'displayName': user.displayName ?? '',
          'createdAt': FieldValue.serverTimestamp(),
        });
      }
    }

    Future<void> signOut() => FirebaseAuth.instance.signOut();

`lib/auth/login_screen.dart` is a centered "Sign in with Google" button calling `signInWithGoogle()`, with a try/catch that shows a SnackBar on failure. Locally the emulator popup lets the tester add/select a mock Google account; the `authStateChanges` stream then flips the gate to the closet.


### Phase 3 — Backend signed image-download endpoint


This is the only backend change, additive and read-only. In `fastapi-service`:

1. `app/ports/` — add to `ImageStoragePort`:

        async def get_signed_download_url(
            self, user_id: str, item_id: str, expiration_seconds: int = 3600
        ) -> str: ...

2. `app/adapters/r2_image_storage.py` — implement it by reusing the existing helper and presign client:

        async def get_signed_download_url(
            self, user_id: str, item_id: str, expiration_seconds: int = 3600
        ) -> str:
            return self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket,
                        "Key": self.image_path_for(user_id, item_id)},
                ExpiresIn=expiration_seconds,
            )

   (`get_download_url(image_path)` already exists; the new method is the user-id/item-id variant that keeps the key convention in one place, mirroring `get_signed_upload_url`.)

3. `app/use_cases/closet/get_download_url.py` — a thin use case mirroring `GetUploadUrlUseCase`:

        class GetDownloadUrlUseCase:
            def __init__(self, image_storage: ImageStoragePort):
                self.image_storage = image_storage
            async def execute(self, user_id: str, item_id: str) -> str:
                return await self.image_storage.get_signed_download_url(user_id, item_id)

   Export it from `app/use_cases/closet/__init__.py`.

4. `app/dependencies.py` — add `get_download_url_use_case() -> GetDownloadUrlUseCase` returning `GetDownloadUrlUseCase(get_image_storage())`.

5. `app/handlers/closet_routes.py` — add:

        @router.get("/items/{item_id}/download-url")
        async def get_download_url(
            item_id: str,
            user_id: str = Depends(verify_firebase_token),
            use_case: GetDownloadUrlUseCase = Depends(get_download_url_use_case),
        ):
            url = await use_case.execute(user_id, item_id)
            return {"download_url": url}

   Authorization is implicit: the key is built from the token's `uid`, so a user can only fetch URLs for their own objects. The endpoint does not verify existence — a missing object simply yields a URL that GETs `404`, which the client renders as a broken-image fallback.

Add a route test (Phase 9) asserting `401` without a token and `200 {"download_url": ...}` with the dependency-overridden token.


### Phase 4 — Closet list via realtime listener with signed-URL thumbnails (M2-11, read)


`lib/closet/closet_item.dart` — a plain model with `fromFirestore(String id, Map data)` mapping `status`, `category`, `tags`, `colors`, `season` (the raw `imageUrl` key is not used for display; the download URL comes from the backend).

`lib/closet/closet_screen.dart` — a `StreamBuilder<QuerySnapshot>` on:

    FirebaseFirestore.instance
        .collection('users').doc(uid).collection('closet')
        .orderBy('createdAt', descending: true)
        .snapshots()

Render a responsive grid of cards. Each card shows the thumbnail, a status badge (`PROCESSING` amber spinner, `READY` green, `ERROR` red), and, when `READY`, the category and first few tags. An empty closet shows a friendly "Add your first item" empty state. The AppBar holds a sign-out action and an item count (`N / 20`).

`lib/closet/thumbnail.dart` — a small widget that resolves the signed GET URL for an item id and renders it, caching per session to avoid refetching on every rebuild:

    class DownloadUrlCache {
      static final Map<String, Future<String>> _cache = {};
      static Future<String> urlFor(String itemId) =>
          _cache.putIfAbsent(itemId, () => api.getDownloadUrl(itemId));
    }

The thumbnail is a `FutureBuilder<String>` on `DownloadUrlCache.urlFor(item.id)` rendering `Image.network(url)` with a loading spinner and a broken-image fallback. (Presigned GET URLs need no CORS for `<img>`; the 1-hour TTL outlives a browsing session.)

Because the backend worker updates the same Firestore document, a `PROCESSING` card re-renders as `READY`/`ERROR` automatically through this stream — no polling. The object exists from upload time (the PUT precedes `complete`), so thumbnails render even while `PROCESSING`.


### Phase 5 — Upload flow (M2-11, upload)


`lib/api/api_client.dart` — a thin wrapper over `http` that attaches the ID token:

    Future<String> _token() async =>
        (await FirebaseAuth.instance.currentUser!.getIdToken())!;
    // GET {apiBase}/closet/upload-url?item_id=...      -> {upload_url, item_id}
    // GET {apiBase}/closet/items/{id}/download-url      -> {download_url}
    // POST {apiBase}/closet/items/{id}/complete         -> {item_id, status}
    // DELETE {apiBase}/closet/items/{id}                -> 204

Map a `429` from upload-url to a typed `ClosetFullException`.

`lib/closet/upload_service.dart` orchestrates one upload:

1. `final itemId = const Uuid().v4();`
2. Pick bytes: `final picked = await ImagePicker().pickImage(source: ImageSource.gallery);` then `final bytes = await picked.readAsBytes();` (web returns `Uint8List`).
3. `final uploadUrl = await api.getUploadUrl(itemId);` (catch `ClosetFullException` → caller shows "Closet is full (20 items)").
4. `await http.put(Uri.parse(uploadUrl), headers: {'Content-Type': 'image/jpeg'}, body: bytes);` — direct to storage; assert `200`. The `Content-Type` must be exactly `image/jpeg` to match the signed URL.
5. `await api.complete(itemId);` — backend writes the `PROCESSING` doc and enqueues the worker.

The new card appears via the Phase 4 listener the instant `complete` writes the document; no client-side list mutation is needed. Wire this to an upload FAB on `ClosetScreen` with a progress indicator and success/error SnackBars.

Note on image format: `image_picker` may return PNG bytes; for MVP they are stored under the `.jpg` key and sent with the `image/jpeg` header (storage does not transcode, and Gemini analysis accepts the bytes). This is acceptable per the backend contract; constraining the picker to JPEG is optional and not required for acceptance.


### Phase 6 — Delete flow (M2-11, delete)


On each card, a delete affordance opens an `AlertDialog`; on confirm, `await api.deleteItem(itemId)` (`DELETE /closet/items/{id}`). On `204` the Firestore document is gone and the listener removes the card. A `404` (already deleted) is treated as success. Show an error SnackBar on other failures.


### Phase 7 — Firestore Security Rules + rules test (M2-12)


Create `firestore.rules` at the repo root:

    rules_version = '2';
    service cloud.firestore {
      match /databases/{database}/documents {
        // A user owns their profile document.
        match /users/{userId} {
          allow read: if request.auth != null && request.auth.uid == userId;
          allow create, update: if request.auth != null && request.auth.uid == userId;
          allow delete: if false;

          // Closet items are readable by the owner; all writes go through the
          // backend Admin SDK (which bypasses rules), so the client cannot write.
          match /closet/{itemId} {
            allow read: if request.auth != null && request.auth.uid == userId;
            allow write: if false;
          }
        }
        // Everything else is denied by default.
      }
    }

Reference it from `firebase.json` (add the `firestore` block; keep the existing `auth` emulator):

    {
      "firestore": { "rules": "firestore.rules" },
      "emulators": {
        "auth": { "host": "0.0.0.0", "port": 9099 },
        "firestore": { "host": "0.0.0.0", "port": 8080 }
      }
    }

Create `firebase/` with a Node test package (`firebase/package.json` depending on `@firebase/rules-unit-testing` and a test runner) and `firebase/firestore-rules.test.mjs` that loads `../firestore.rules` and asserts:

- Owner can `get` `users/{uid}` and `get`/`list` `users/{uid}/closet/{item}`.
- A different signed-in user is denied `get` on another user's `users/{uid}/closet/{item}` and on `users/{uid}`.
- The owner is denied `set`/`update`/`delete` on `users/{uid}/closet/{item}` (writes are backend-only).
- The owner can `create` their own `users/{uid}` profile (the Phase 2 bootstrap path).

Run it via `firebase emulators:exec --only firestore --project gen-fashion-local "npm test"` from `firebase/`, which starts the rule-enforcing emulator just for the test (Decision Log explains why this is separate from `make dev`).


### Phase 8 — Local-stack adjustment


In `docker-compose.yml`, add CORS to the `minio` service so browser preflight + `PUT` succeed:

    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
      - MINIO_API_CORS_ALLOW_ORIGIN=http://localhost:8088

The bucket stays private — no anonymous policy is set. The backend plan's bucket-create step (`mc mb -p local/gen-fashion-images`) is unchanged and remains the only bucket setup needed; thumbnails are served via signed GET URLs, not public reads.


### Phase 9 — Tests


- Backend route test (`fastapi-service/tests/...`): `GET /closet/items/{id}/download-url` returns `401` without a token and `200 {"download_url": ...}` with the `verify_firebase_token` dependency overridden, using a `FakeImageStorage` whose `get_signed_download_url` returns a sentinel URL. Run `python -m pytest -q` and confirm the suite still passes (previously `28 passed`, now one more).
- Flutter widget test (`flutter-web-app/test/closet_grid_test.dart`): pump the closet grid with an injected list of `ClosetItem`s and assert a `PROCESSING` badge, a `READY` badge with category text, and the empty-state widget render correctly. Keep Firestore and network out by rendering the pure grid widget from a passed-in list and stubbing the thumbnail.
- Flutter unit test (`test/api_client_test.dart`): with a mocked `http.Client`, assert `getUploadUrl` builds `/closet/upload-url?item_id=...` with the bearer header and maps `429` to `ClosetFullException`; `getDownloadUrl` parses `download_url`; `deleteItem` issues `DELETE` and treats `204`/`404` as success.
- Rules test: Phase 7 suite passes.
- Documented manual browser E2E: see *Validation and Acceptance*.

`flutter analyze` must report no issues and `flutter test` and the backend `pytest -q` must pass before any matrix row flips to ✅.


## Concrete Steps


### Working directory


Unless stated otherwise, run from `/Users/ran/my-app/gen-fashion`.


### Step 1 — Prerequisites


Install the Flutter SDK (stable channel, web enabled) and confirm:

    flutter --version
    flutter config --enable-web
    flutter doctor

Install the Node tooling for the rules test (a JRE is required by the Firestore emulator):

    npm install -g firebase-tools
    java -version   # any JRE 11+; install one if absent


### Step 2 — Add the backend download-url endpoint


Apply the Phase 3 edits in `fastapi-service` (`app/ports`, `app/adapters/r2_image_storage.py`, `app/use_cases/closet/get_download_url.py` + `__init__.py`, `app/dependencies.py`, `app/handlers/closet_routes.py`) and the Phase 9 route test, then:

    cd /Users/ran/my-app/gen-fashion/fastapi-service
    python -m pytest -q

Expected: the suite passes with one additional test (the previous run reported `28 passed`).


### Step 3 — Scaffold the app


    cd /Users/ran/my-app/gen-fashion
    flutter create --platforms web --org com.genfashion flutter-web-app

Then apply the Phase 0–2 and 4–6 edits (`pubspec.yaml` deps, `lib/config.dart`, `lib/main.dart`, `lib/auth/*`, `lib/closet/*`, `lib/api/api_client.dart`), running after each:

    cd flutter-web-app && flutter pub get && flutter analyze

Expected: `flutter pub get` resolves; `flutter analyze` reports `No issues found!`.


### Step 4 — Bring up the backend stack


    cd /Users/ran/my-app/gen-fashion
    # apply the Phase 8 docker-compose change first
    make dev

Expected: `elasticsearch`, `firestore-emulator`, `firebase-auth-emulator`, `minio`, `fastapi-service` come up healthy; `curl -s http://localhost:8000/health` returns `{"status":"ok"}`. Ensure the bucket exists (backend plan's `mc mb -p local/gen-fashion-images`); no anonymous policy is needed.


### Step 5 — Run the app and do the browser E2E


    cd /Users/ran/my-app/gen-fashion && make web

In the launched Chrome window at `http://localhost:8088`:

1. Confirm the login screen appears and the closet is unreachable while signed out.
2. Click "Sign in with Google"; in the emulator popup add/select a mock account. The closet screen loads. Confirm a `users/{uid}` doc now exists (read it from the Firestore emulator or observe the count chip).
3. Upload a JPEG. A new card appears as `PROCESSING` with its thumbnail rendered (via the signed GET URL).
4. With a real `GEMINI_API_KEY` in the environment, the card flips to `READY` with category/tags within seconds; with the default dummy key it flips to `ERROR` (still visible). Either transition proves the live listener.
5. Delete the item via its menu and confirm; the card disappears.

Record the run (screenshots or a short note of each transition) in *Artifacts and Notes*.


### Step 6 — Run the remaining automated checks


    cd /Users/ran/my-app/gen-fashion/flutter-web-app && flutter analyze && flutter test
    cd /Users/ran/my-app/gen-fashion/firebase && npm install && \
      firebase emulators:exec --only firestore --project gen-fashion-local "npm test"

Expected: `flutter test` reports all widget/unit tests passing; the rules suite reports all allow/deny assertions passing.


## Validation and Acceptance


Acceptance is the M2 client behavior, observed against the local stack:

- **M2-1:** Signed out, the app shows only the login screen (closet unreachable). `signInWithPopup(GoogleAuthProvider())` against the Auth Emulator authenticates the user; on first sign-in `users/{uid}` is created with `displayName` and `createdAt`. Sign-out returns to the login screen.
- **M2-11 (read):** The closet grid is driven by the `users/{uid}/closet` realtime listener; a backend status change (`PROCESSING` → `READY`/`ERROR`) re-renders the affected card with no manual refresh, `READY` cards show category/tags, and thumbnails render via the backend signed GET URL with the bucket kept private.
- **M2-11 (upload):** Picking an image yields a signed URL, a direct `PUT` to storage, and a `complete` call; the new card appears via the listener. At 20 items the upload surfaces the backend `429` as "Closet is full".
- **M2-11 (delete):** Confirming delete calls `DELETE /closet/items/{id}`; on `204` the card disappears; `404` is treated as already-deleted.
- **M2-12:** The `@firebase/rules-unit-testing` suite passes: owner reads of `users/{uid}` and `users/{uid}/closet/*` are allowed; cross-user reads are denied; client writes to `users/{uid}/closet/*` are denied; the owner can create their own `users/{uid}` profile.
- **Backend:** `GET /closet/items/{id}/download-url` returns `401` without a token and a signed GET URL with one; `python -m pytest -q` in `fastapi-service` still passes.
- **Static/tests:** `flutter analyze` reports no issues; `flutter test` passes.

Only when each requirement above is observed does its matrix row move to ✅. Until then M2-1/M2-11/M2-12 stay 🟡.


## Idempotence and Recovery


- The backend download-url endpoint is stateless and idempotent: each call returns a fresh signed URL for the same key; it writes nothing.
- `flutter create` is safe to re-run into the same directory; it does not overwrite hand-edited `lib/` files (it skips existing files). If scaffolding looks wrong, delete `flutter-web-app/` and re-run Step 3, then re-apply the `lib/` edits.
- `_ensureUserDoc` reads before writing, so repeated logins do not overwrite `createdAt`; the write is a one-time create.
- Upload uses a fresh `uuid` per attempt; a retried upload creates a new item rather than corrupting an existing one. A failed `PUT` before `complete` leaves no Firestore document (nothing to clean up).
- The thumbnail URL cache is per-session and self-refilling; clearing it (reload) simply re-fetches URLs.
- The rules test runs in an ephemeral `firebase emulators:exec` emulator and leaves no state behind; it is safe to run repeatedly and in CI.
- `make clean` (`docker-compose down -v`) discards emulator/MinIO data; re-run `make dev` and ensure the bucket exists to rebuild.


## Artifacts and Notes


To be filled during execution: the backend `pytest -q` output, `flutter analyze`/`flutter test` output, the rules-test transcript, and a short record (or screenshots) of the browser E2E showing the rendered thumbnail, the `PROCESSING` → `READY`/`ERROR` transition, and the post-delete empty card. Note any dependency version adjustments made at `flutter pub get` time.


## Interfaces and Dependencies


- **`firebase_core`, `firebase_auth`, `cloud_firestore`** (new) — Firebase init, Google popup sign-in + emulator wiring (M2-1), and the closet realtime listener (M2-11 read). Local auth/Firestore go to the emulators; production uses the real project values via `--dart-define`.
- **`http`** (new) — calls to the FastAPI closet endpoints (upload-url, download-url, complete, delete) and the direct `PUT` to the signed storage URL.
- **`image_picker`** (new) — picks image bytes in the browser for upload.
- **`uuid`** (new) — client-side `item_id` generation (§6.7 requires the client to supply it).
- **`@firebase/rules-unit-testing` + `firebase-tools` + a JRE** (new, dev only) — deterministic enforcement test for `firestore.rules` (M2-12), run via `firebase emulators:exec --only firestore`.
- **Backend signed-download endpoint** (new, in `fastapi-service`) — `GET /closet/items/{id}/download-url`, built on the existing `R2ImageStorage.get_download_url`/`image_path_for` and the existing `verify_firebase_token` dependency. Keeps storage private in both MinIO (dev) and R2 (prod).
- **Backend (otherwise unchanged):** `fastapi-service` upload/complete/delete routes at `http://localhost:8000`, the Firebase Auth Emulator (`:9099`), the gcloud Firestore emulator (`:8080`), and MinIO (`:9000`) from `make dev`. This plan adds only `MINIO_API_CORS_ALLOW_ORIGIN` to the stack and the additive endpoint above.
- **Out of this plan:** any change to existing backend behavior or to `adk-agent-service`; the LINE/LIFF auth flow (§10.2, Phase 1b); and all M3–M6 work. Live rule enforcement inside `make dev` is intentionally deferred (Decision Log).
