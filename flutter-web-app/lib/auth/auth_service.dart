import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../config.dart';

/// Encapsulates the Google popup sign-in and the first-login `users/{uid}`
/// bootstrap (M2-1, Decision Log: client creates the profile doc).
class AuthService {
  static const _localEmail = 'local@example.com';
  static const _localPassword = 'Password123!';

  /// Pops the Google sign-in dialog (against the Auth Emulator's mock provider
  /// locally; the real provider in production) and ensures the `users/{uid}`
  /// document exists.
  Future<UserCredential> signInWithGoogle({
    void Function(String language)? onLanguage,
  }) async {
    final cred = AppConfig.useEmulators
        ? await _signInWithLocalEmulatorUser()
        : await FirebaseAuth.instance.signInWithPopup(GoogleAuthProvider());
    final user = cred.user;
    if (user != null) {
      final language = await _ensureUserDoc(user);
      onLanguage?.call(language);
    }
    return cred;
  }

  Future<UserCredential> _signInWithLocalEmulatorUser() async {
    try {
      return await FirebaseAuth.instance.signInWithEmailAndPassword(
        email: _localEmail,
        password: _localPassword,
      );
    } on FirebaseAuthException catch (e) {
      if (e.code != 'user-not-found' && e.code != 'invalid-credential') {
        rethrow;
      }
      return FirebaseAuth.instance.createUserWithEmailAndPassword(
        email: _localEmail,
        password: _localPassword,
      );
    }
  }

  Future<String> _ensureUserDoc(User user) async {
    final ref = FirebaseFirestore.instance.collection('users').doc(user.uid);
    final snap = await ref.get();
    if (!snap.exists) {
      await ref.set({
        'displayName': user.displayName ?? '',
        'language': 'ja',
        'createdAt': FieldValue.serverTimestamp(),
      });
      return 'ja';
    }
    final raw = snap.data()?['language'];
    final language = raw is String && (raw == 'ja' || raw == 'en') ? raw : 'ja';
    if (raw != language) {
      await ref.set({'language': language}, SetOptions(merge: true));
    }
    return language;
  }

  Future<void> signOut() => FirebaseAuth.instance.signOut();
}
