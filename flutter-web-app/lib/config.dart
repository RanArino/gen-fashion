/// Compile-time configuration sourced from `--dart-define` flags so no secrets
/// are baked into the repo. Defaults match the local `make dev` stack so the
/// app boots out-of-the-box for a fresh clone.
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );
  static const bool useEmulators = bool.fromEnvironment(
    'USE_EMULATORS',
    defaultValue: true,
  );
  static const String firebaseProjectId = String.fromEnvironment(
    'FIREBASE_PROJECT_ID',
    defaultValue: 'gen-fashion-local',
  );
  static const String authEmulatorHost = String.fromEnvironment(
    'AUTH_EMULATOR_HOST',
    defaultValue: 'localhost',
  );
  static const int authEmulatorPort = int.fromEnvironment(
    'AUTH_EMULATOR_PORT',
    defaultValue: 9099,
  );
  static const String firestoreEmulatorHost = String.fromEnvironment(
    'FIRESTORE_EMULATOR_HOST',
    defaultValue: 'localhost',
  );
  static const int firestoreEmulatorPort = int.fromEnvironment(
    'FIRESTORE_EMULATOR_PORT',
    defaultValue: 8080,
  );
}
