import 'package:firebase_core/firebase_core.dart';

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
  static const bool e2eAutoSignIn = bool.fromEnvironment(
    'E2E_AUTO_SIGN_IN',
    defaultValue: false,
  );
  static const bool e2eAutoRun = bool.fromEnvironment(
    'E2E_AUTO_RUN',
    defaultValue: false,
  );
  static const String firebaseProjectId = String.fromEnvironment(
    'FIREBASE_PROJECT_ID',
    defaultValue: 'gen-fashion-local',
  );
  static const String firebaseApiKey = String.fromEnvironment(
    'FIREBASE_API_KEY',
    defaultValue: 'demo-local-api-key',
  );
  static const String firebaseAppId = String.fromEnvironment(
    'FIREBASE_APP_ID',
    defaultValue: '1:000000000000:web:0000000000000000',
  );
  static const String firebaseMessagingSenderId = String.fromEnvironment(
    'FIREBASE_MESSAGING_SENDER_ID',
    defaultValue: '000000000000',
  );
  static const String firebaseAuthDomain = String.fromEnvironment(
    'FIREBASE_AUTH_DOMAIN',
    defaultValue: 'gen-fashion-local.firebaseapp.com',
  );
  static const String firebaseStorageBucket = String.fromEnvironment(
    'FIREBASE_STORAGE_BUCKET',
    defaultValue: 'gen-fashion-local.appspot.com',
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

  static const FirebaseOptions firebaseOptions = FirebaseOptions(
    apiKey: firebaseApiKey,
    appId: firebaseAppId,
    messagingSenderId: firebaseMessagingSenderId,
    projectId: firebaseProjectId,
    authDomain: firebaseAuthDomain,
    storageBucket: firebaseStorageBucket,
  );
}
