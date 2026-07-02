# flutter-web-app — gen-fashion closet UI (M2-1, M2-11)

Flutter Web client that drives the M2 closet management flow against the
local `make dev` stack: Google Sign-In (via the Firebase Auth Emulator),
Firestore realtime closet listener, signed upload/delete to the backend.

## Prerequisites

- Flutter SDK (stable, web enabled): `flutter config --enable-web`
- `make dev` running from the repo root (FastAPI on `:8000`, Auth Emulator on
  `:9099`, Firestore Emulator on `:8080`, MinIO on `:9000`)
- Ensure the MinIO bucket `gen-fashion-images` exists (see the M2 backend
  ExecPlan; create it once with `mc mb -p local/gen-fashion-images`).

## Run

From the repo root:

```bash
make web
```

This is equivalent to:

```bash
cd flutter-web-app
flutter run -d chrome --web-port 8088 \
  --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=USE_EMULATORS=true \
  --dart-define=FIREBASE_PROJECT_ID=gen-fashion-local \
  --dart-define=FIREBASE_API_KEY=AIzaSyDLocalEmulatorOnlyKey00000000000 \
  --dart-define=FIREBASE_APP_ID=1:000000000000:web:0000000000000000 \
  --dart-define=FIREBASE_MESSAGING_SENDER_ID=000000000000 \
  --dart-define=FIREBASE_AUTH_DOMAIN=gen-fashion-local.firebaseapp.com \
  --dart-define=FIREBASE_STORAGE_BUCKET=gen-fashion-local.appspot.com
```

The Chrome window opens at `http://localhost:8088`. Sign-in uses a generated
email/password user against the Auth Emulator — no real OAuth client needed
locally.

For production, pass the real Firebase web config through `--dart-define`
values such as `FIREBASE_API_KEY`, `FIREBASE_APP_ID`,
`FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_PROJECT_ID`,
`FIREBASE_AUTH_DOMAIN`, and `FIREBASE_STORAGE_BUCKET`. Generated
`lib/firebase_options.dart` files are intentionally ignored.

## Tests

```bash
flutter pub get
flutter analyze
flutter test
```

## Layout

- `lib/main.dart` — Firebase init and emulator wiring.
- `lib/auth/` — `AuthGate`, Google Sign-In, first-login `users/{uid}` bootstrap.
- `lib/closet/` — Firestore realtime listener, upload/delete flows, status
  badges, signed-URL thumbnails.
- `lib/api/api_client.dart` — FastAPI HTTP wrapper (signed upload URL, signed
  download URL, complete, delete) with bearer auth.
- `lib/config.dart` — `--dart-define` compile-time settings, including Firebase
  web options with local emulator defaults.
